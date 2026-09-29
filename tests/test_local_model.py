import json
import time
import threading
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


def model(tmp_path, **kwargs):
    from depverify.local_model import LocalModel
    return LocalModel(Path('/not-a-real-model'), {'revision': 'a' * 40}, tmp_path / 'budget.jsonl',
                      {'total_seconds': {'model': 43200}, 'stage_seconds': {'M1': {'model': 900}},
                       'per_call_seconds': {'model': 180, 'execution': 10}}, 'M1',
                      worker_target=fake_worker, **kwargs)


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
        assert task.contract in messages[-1]['content']
        assert 'bench/private' not in text
        assert 'independent_expected' not in text
        assert 'previous_verdict' not in text
        if role != 'proposal':
            assert json.loads(messages[-1]['content'])['replacement'] == proposal


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
