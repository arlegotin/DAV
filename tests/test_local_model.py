import json
import time
import threading
import os
import struct
from types import SimpleNamespace
from pathlib import Path
import pytest
from depverify.pipeline import resume_attempts
from depverify.tasks import load_pilot


def fake_worker(connection, model_path):
    connection.send_bytes(json.dumps({'status': 'ready', 'peak_memory_bytes': 0}).encode())
    while True:
        request = json.loads(connection.recv_bytes())
        if request['messages'][0]['content'] == 'hang':
            time.sleep(10)
        connection.send_bytes(json.dumps({'status': 'ok', 'text': 'reply', 'input_tokens': 4,
                                         'output_tokens': 1, 'prompt_tps': 10, 'generation_tps': 10}).encode())


def unread_worker(connection, model_path):
    connection.send_bytes(b'{"status":"ready"}')
    time.sleep(10)


def partial_worker(connection, model_path):
    connection.send_bytes(b'{"status":"ready"}')
    connection.recv_bytes()
    os.write(connection.fileno(),struct.pack('!i',60000)+b'{')
    time.sleep(10)


def model(tmp_path, **kwargs):
    from depverify.local_model import LocalModel
    return LocalModel(Path('/not-a-real-model'), {'revision': 'a' * 40}, tmp_path / 'budget.jsonl',
                      {'total_seconds': {'model': 43200}, 'stage_seconds': {'M1': {'model': 900}},
                       'per_call_seconds': {'model': 180, 'execution': 10}}, 'M1',
                      worker_target=kwargs.pop('worker_target',fake_worker), **kwargs)


def test_chat_template_overflow_does_not_call_generation():
    from depverify.local_model import infer
    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            assert kwargs == {'tokenize': True, 'add_generation_prompt': True}
            return [1] * 3073
    def generate(*args, **kwargs):
        raise AssertionError('over-budget input must not generate')
    result = infer(None, Tokenizer(), [{'role': 'user', 'content': 'x'}], 'proposal', 1, .2, generate)
    assert result['status'] == 'input_over_budget'
    assert result['input_tokens'] == 3073
    assert result['output_tokens'] == 0


def test_prompt_contains_only_fixed_public_inputs_and_no_previous_verdict():
    from depverify.local_model import assemble_messages
    task = load_pilot()[0]
    proposal = 'def solve(x): return True\n'
    for role in ('proposal', 'R1', 'R2', 'D'):
        messages = assemble_messages(task, role, proposal if role != 'proposal' else None)
        text = json.dumps(messages)
        assert task.contract in messages[-2]['content']
        assert 'bench/private' not in text
        assert 'independent_expected' not in text
        assert 'previous_verdict' not in text
        if role != 'proposal':
            assert json.loads(messages[-2]['content'].split('\n')[1])['replacement'] == proposal


def test_worker_timeout_kills_model_and_retains_all_costs(tmp_path):
    local = model(tmp_path, timeout=.05)
    # Spawn startup is allowed a normal envelope; only this request gets tiny timeout.
    local.start(timeout=5)
    result = local.generate([{'role': 'user', 'content': 'hang'}], role='R1', seed=1, temperature=0)
    assert result['status'] == 'model_timeout'
    assert local.worker_alive is False
    state = resume_attempts(tmp_path / 'budget.jsonl')
    assert state['model_seconds'] >= .05
    assert state['reserved_model_seconds'] == 0
    assert len(state['attempts']) == 2
    local.close()


def test_one_resident_worker_and_fresh_requests(tmp_path):
    first = model(tmp_path)
    second = model(tmp_path / 'other')
    try:
        first.start()
        with pytest.raises(RuntimeError):
            second.start()
        a = first.generate([{'role': 'user', 'content': 'one'}], role='proposal', seed=2, temperature=.2)
        b = first.generate([{'role': 'user', 'content': 'two'}], role='R2', seed=3, temperature=0)
        assert a['text'] == b['text'] == 'reply'
        assert a['attempt_id'] != b['attempt_id']
    finally:
        first.close()
        second.close()


def test_concurrent_request_is_rejected_before_another_call(tmp_path):
    local = model(tmp_path, timeout=.2)
    try:
        local.start()
        thread = threading.Thread(target=lambda: local.generate([{'role': 'user', 'content': 'hang'}],
                                                                 role='R1', seed=1, temperature=0))
        thread.start()
        until = time.monotonic() + 1
        while not local._request.locked() and time.monotonic() < until:
            time.sleep(.001)
        with pytest.raises(RuntimeError):
            local.generate([{'role': 'user', 'content': 'second'}], role='R2', seed=2, temperature=0)
        thread.join(timeout=2)
        assert not thread.is_alive()
        assert len(resume_attempts(tmp_path / 'budget.jsonl')['attempts']) == 2
    finally:
        local.close()


def test_load_uses_declared_chat_eos_instead_of_stale_conversion_eos(tmp_path):
    from depverify.local_model import load_options
    (tmp_path/'config.json').write_text(json.dumps({'eos_token_id':151643}))
    (tmp_path/'tokenizer_config.json').write_text(json.dumps({'eos_token':'<|im_end|>'}))
    (tmp_path/'tokenizer.json').write_text(json.dumps({'added_tokens':[{'content':'<|im_end|>','id':151645}]}))
    assert load_options(tmp_path) == {'tokenizer_config':{'trust_remote_code':False},
                                      'model_config':{'eos_token_id':151645}}


def test_public_formatting_example_precedes_task_without_repairing_generated_bytes():
    from depverify.local_model import assemble_messages
    task=load_pilot()[0]
    messages=assemble_messages(task,'proposal')
    assert [m['role'] for m in messages]==['system','user','assistant','user','assistant']
    assert messages[2]['content']=='def solve(x):\n    return x\n'
    assert task.contract not in messages[1]['content']
    assert task.contract in messages[-2]['content']
    assert messages[-1]['content']=='def solve(x):\n'


def test_response_prefix_is_prompted_before_generation_and_all_returned_bytes_survive():
    from depverify.local_model import infer
    class Tokenizer:
        def apply_chat_template(self,messages,**kwargs):
            assert kwargs=={'tokenize':True,'add_generation_prompt':False,'continue_final_message':True}
            assert messages[-1]['content']=='def solve(x):\n'
            return [1]*100
    generated='    return x\n'
    result=infer(None,Tokenizer(),[{'role':'assistant','content':'def solve(x):\n'}],
                 'proposal',1,.2,lambda *args:{'status':'ok','text':generated,'output_tokens':3})
    assert result['text']=='def solve(x):\n'+generated
    assert result['generated_text']==generated
    assert result['input_tokens']==100 and result['output_tokens']==3


def test_generation_decodes_tokens_faithfully_instead_of_cleaned_stream_display():
    from depverify.local_model import consume_generation
    class Tokenizer:
        eos_token_ids={99}
        def decode(self,tokens,**kwargs):
            assert tokens==[1,2]
            assert kwargs=={'clean_up_tokenization_spaces':False,'skip_special_tokens':False}
            return '    first = 1\n    return first\n'
    base={'prompt_tokens':10,'generation_tokens':3,'prompt_tps':100,'generation_tps':100,'peak_memory':1}
    responses=[SimpleNamespace(**base,token=1,text='   first = 1\n',finish_reason=None),
               SimpleNamespace(**base,token=2,text='    return first\n',finish_reason=None),
               SimpleNamespace(**base,token=99,text='',finish_reason='stop')]
    result=consume_generation(Tokenizer(),responses)
    assert result['text']=='    first = 1\n    return first\n'
    assert result['generated_token_ids']==[1,2]


@pytest.mark.parametrize('worker,content',[(unread_worker,'x'*60000),(partial_worker,'x')],ids=['blocked-send','partial-response'])
def test_watchdog_covers_transmission_and_partial_response_and_restart(tmp_path,worker,content):
    local=model(tmp_path,worker_target=worker,timeout=.05)
    try:
        local.start(timeout=5)
        started=time.monotonic()
        result=local.generate([{'role':'user','content':content}],role='R1',seed=1,temperature=0)
        assert time.monotonic()-started<1.5
        assert result['status']=='model_timeout'
        assert not local.worker_alive
        assert resume_attempts(tmp_path/'budget.jsonl')['reserved_model_seconds']==0
        local.target=fake_worker
        result=local.generate([{'role':'user','content':'retry'}],role='R1',seed=1,temperature=0)
        assert result['status']=='ok'
    finally:
        local.close()


def test_changed_assets_refuse_before_worker_load(tmp_path):
    from depverify.records import sha256_bytes
    asset=tmp_path/'tokenizer_config.json'
    asset.write_text('{"eos_token":"old"}')
    identity={'revision':'a'*40,'asset_sha256':{asset.name:sha256_bytes(asset.read_bytes())}}
    local=model(tmp_path)
    local.path=tmp_path
    local.identity=identity
    asset.write_text('{"eos_token":"changed"}')
    with pytest.raises(RuntimeError,match='setup failed'):
        local.start()
    assert not local.worker_alive


def test_asset_inventory_rejects_unexpected_weights_and_missing_tokenizer(tmp_path):
    from depverify.local_model import verify_assets
    from depverify.records import sha256_bytes
    file=tmp_path/'tokenizer.json';file.write_text('{}')
    identity={'asset_sha256':{'tokenizer.json':sha256_bytes(file.read_bytes())}}
    (tmp_path/'unexpected.safetensors').write_bytes(b'weights')
    with pytest.raises(ValueError):verify_assets(tmp_path,identity)
    (tmp_path/'unexpected.safetensors').unlink();file.unlink()
    with pytest.raises(ValueError):verify_assets(tmp_path,identity)
