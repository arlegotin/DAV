"""One native resident MLX worker; bounded JSON IPC and lazy MLX imports."""
import multiprocessing
import os
from pathlib import Path
import threading
import time
import uuid

from .records import canonical_json, parse_json, read_json, sha256_bytes, write_json_atomic
from .pipeline import reserve, settle

_RESIDENT = threading.Lock()


def assemble_messages(task, role, proposal=None):
    if role not in ('proposal', 'R1', 'R2', 'D'):
        raise ValueError('unknown model action')
    prompt = Path(__file__).resolve().parents[2] / 'prompts' / (role + '.txt')
    packet = task.source_manifest['packets'][{'proposal': 'A', 'R1': 'A', 'R2': 'B', 'D': 'D'}[role]]
    if sha256_bytes(packet['body'].encode()) != packet['sha256']:
        raise ValueError('source packet hash changed')
    fields = {'contract': task.contract, 'source_packet': packet['body']}
    if role == 'proposal':
        fields.update(files=dict(task.base_files), public_tests=task.public_tests, editable_path=task.editable_path)
    else:
        if not isinstance(proposal, str):
            raise ValueError('reviews require the frozen replacement')
        fields['replacement'] = proposal
    output = ('Return only raw Python source, starting with imports or def. Do not wrap it in Markdown.' if role=='proposal'
              else 'Return only a JSON object, starting with { and ending with }. Exactly two keys: verdict (PASS, FAIL, or UNKNOWN) and reason. Do not use Markdown.')
    return [{'role': 'system', 'content': prompt.read_text()},
            {'role': 'user', 'content': 'Task materials (JSON data):\n' + canonical_json(fields).decode() + '\n\n' + output}]


def load_options(model_path):
    """Honor the pinned tokenizer's declared chat EOS without editing cached assets."""
    path = Path(model_path)
    config = read_json(path/'tokenizer_config.json')
    eos = config['eos_token']
    eos = eos['content'] if isinstance(eos, dict) else eos
    ids = [token['id'] for token in read_json(path/'tokenizer.json')['added_tokens'] if token['content']==eos]
    if len(ids)!=1 or type(ids[0]) is not int:
        raise ValueError('ambiguous tokenizer EOS identity')
    return {'tokenizer_config':{'trust_remote_code':False},'model_config':{'eos_token_id':ids[0]}}


def infer(model, tokenizer, messages, role, seed, temperature, generation):
    if role not in ('proposal', 'R1', 'R2', 'D'):
        raise ValueError('unknown generation role')
    tokens = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
    cap = 512 if role == 'proposal' else 128
    base = {'input_tokens': len(tokens), 'output_tokens': 0,
            'prompt_hash': sha256_bytes(canonical_json({'messages': messages, 'input_ids': tokens})), 'text': ''}
    if len(tokens) > 3072 or len(tokens) + cap > 4096:
        return base | {'status': 'input_over_budget'}
    result = generation(model, tokenizer, tokens, cap, seed, temperature)
    if not 0 <= result['output_tokens'] <= cap:
        raise ValueError('generation violated its frozen token cap')
    return base | result


def _native_generation(model, tokenizer, tokens, cap, seed, temperature):
    import mlx.core as mx
    from mlx_lm import stream_generate
    from mlx_lm.sample_utils import make_sampler
    mx.random.seed(seed)
    chunks, final = [], None
    # No transcript or KV cache is supplied: every request starts fresh.
    for response in stream_generate(model, tokenizer, tokens, max_tokens=cap, sampler=make_sampler(temp=temperature)):
        chunks.append(response.text)
        final = response
    if final is None:
        raise RuntimeError('generation returned no measurement')
    return {'status': 'truncated' if final.finish_reason == 'length' else 'ok', 'text': ''.join(chunks),
            'input_tokens': final.prompt_tokens, 'output_tokens': final.generation_tokens,
            'prompt_tps': final.prompt_tps, 'generation_tps': final.generation_tps,
            'peak_memory_bytes': int(final.peak_memory * 1e9), 'finish_reason': final.finish_reason}


def _mlx_worker(connection, model_path):
    try:
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        os.environ['TOKENIZERS_PARALLELISM'] = 'false'
        import mlx.core as mx
        from mlx_lm import load
        options = load_options(model_path)
        model, tokenizer = load(str(model_path), **options, lazy=False)
        connection.send_bytes(canonical_json({'status': 'ready', 'peak_memory_bytes': mx.get_peak_memory(),
                                             'load_options': options,
                                             'chat_template_hash': sha256_bytes(str(tokenizer.chat_template).encode())}))
        while True:
            request = parse_json(connection.recv_bytes(65536).decode())
            result = infer(model, tokenizer, request['messages'], request['role'], request['seed'],
                           request['temperature'], _native_generation)
            connection.send_bytes(canonical_json(result))
            mx.clear_cache()
    except EOFError:
        return
    except BaseException as exc:
        try:
            connection.send_bytes(canonical_json({'status': 'infrastructure_error', 'text': '',
                                                  'input_tokens': 0, 'output_tokens': 0,
                                                  'error_type': type(exc).__name__, 'error': str(exc)[:1000]}))
        except (OSError, EOFError):
            pass


class LocalModel:
    def __init__(self, model_path, identity, ledger, limits, stage, *, worker_target=None, timeout=180., record_dir=None):
        if not 0 < timeout <= 180:
            raise ValueError('model timeout exceeds its envelope')
        self.path, self.identity, self.ledger = Path(model_path), dict(identity), Path(ledger)
        self.limits, self.stage, self.timeout = limits, stage, timeout
        self.target = worker_target or _mlx_worker
        self.record_dir = Path(record_dir) if record_dir else self.ledger.parent / 'model-calls'
        self.process = self.connection = None
        self._resident = False
        self._request = threading.Lock()
        self.startup = None

    @property
    def worker_alive(self):
        return self.process is not None and self.process.is_alive()

    def _kill(self):
        if self.process is not None:
            if self.process.is_alive():
                self.process.kill()
            self.process.join(timeout=1)
            if self.process.is_alive():
                raise RuntimeError('model worker could not be terminated')
            self.process.close()
            self.process = None
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        if self._resident:
            self._resident = False
            _RESIDENT.release()

    def _exchange(self, request, timeout, launch=False):
        attempt = uuid.uuid4().hex
        reservation = reserve(self.ledger, attempt_id='model-' + attempt, stage=self.stage,
                              work_kind='model', allowance_seconds=180., limits=self.limits)
        started = time.monotonic()
        result = {'status': 'infrastructure_error', 'text': '', 'input_tokens': 0, 'output_tokens': 0}
        try:
            if launch:
                context = multiprocessing.get_context('spawn')
                self.connection, child = context.Pipe()
                self.process = context.Process(target=self.target, args=(child, self.path), daemon=True)
                self.process.start()
                child.close()
            else:
                self.connection.send_bytes(canonical_json(request))
            if not self.connection.poll(max(0., min(timeout, 178.) - (time.monotonic() - started))):
                result['status'] = 'model_timeout'
                self._kill()
            else:
                result = parse_json(self.connection.recv_bytes(65536).decode())
                if result['status'] == 'infrastructure_error':
                    self._kill()
        except (OSError, EOFError, ValueError) as exc:
            result.update(status='infrastructure_error', error_type=type(exc).__name__)
            self._kill()
        finally:
            elapsed = time.monotonic() - started
            result.update(attempt_id=attempt, elapsed_seconds=elapsed, timed_out=result['status'] == 'model_timeout',
                          cache_hit=False, identity=self.identity, request_hash=sha256_bytes(canonical_json(request)))
            write_json_atomic(self.record_dir / (attempt + '.json'), result | {'request': request})
            settle(self.ledger, reservation_id=reservation, actual_seconds=elapsed, status=result['status'])
        return result

    def start(self, *, timeout=180.):
        if self.worker_alive:
            return self.startup
        if not _RESIDENT.acquire(blocking=False):
            raise RuntimeError('only one resident model is allowed')
        self._resident = True
        try:
            self.startup = self._exchange({'operation': 'load'}, timeout, launch=True)
            if self.startup['status'] != 'ready':
                self._kill()
                raise RuntimeError('model setup failed: ' + self.startup['status'])
            return self.startup
        except BaseException:
            self._kill()
            raise

    def generate(self, messages, *, role, seed, temperature):
        if role not in ('proposal', 'R1', 'R2', 'D') or type(seed) is not int or seed < 0:
            raise ValueError('invalid fixed generation action/seed')
        if temperature != (.2 if role == 'proposal' else 0):
            raise ValueError('generation configuration changed')
        request = {'messages': messages, 'role': role, 'seed': seed, 'temperature': temperature}
        if len(canonical_json(request)) > 65536:
            raise ValueError('prompt exceeds the bounded transport')
        if not self._request.acquire(blocking=False):
            raise RuntimeError('only one concurrent model request is allowed')
        try:
            self.start()
            return self._exchange(request, self.timeout)
        finally:
            self._request.release()

    def close(self):
        self._kill()
