from collections import Counter
from pathlib import Path
import pytest
from depverify.records import canonical_json, read_json, write_json_atomic
from depverify.tasks import load_pilot
from depverify.collection import eager_ids, schedule, actor_messages, write_once, durable_call, require_pilot_gates, collect_episode


def test_orders_are_balanced_and_seed_schedule_is_fixed():
    tasks = load_pilot()
    rows = schedule(tasks)
    assert rows == schedule(list(reversed(tasks)))
    assert len({tuple(row['order']) for row in rows.values()}) == 24
    for position in range(4):
        assert set(Counter(row['order'][position] for row in rows.values()).values()) == {6}
    assert len({seed for row in rows.values() for seed in row['seeds'].values()}) == 144


def test_eager_selection_and_materials_use_only_public_inputs():
    tasks = load_pilot()
    assert len(eager_ids(tasks)) == 8
    assert eager_ids(tasks) == eager_ids(list(reversed(tasks)))
    task = tasks[0]
    ordinary = actor_messages(task, 'natural')
    eager = actor_messages(task, 'eager')
    assert ordinary[-1] == eager[-1]
    assert ordinary[0:3] == eager[0:3]
    assert 'additional_allowed_packets' not in ordinary[-2]['content']
    assert 'additional_allowed_packets' in eager[-2]['content']
    assert all(word not in canonical_json(eager).decode() for word in ['hidden_expected', 'reference_implementation', 'label'])


def test_missing_gate_refuses_before_generation(tmp_path):
    with pytest.raises(ValueError, match='gate'):
        require_pilot_gates(tmp_path, Path('config.toml'))


def test_completed_record_cannot_be_changed(tmp_path):
    path = tmp_path/'frozen.json'
    write_once(path, {'bad_proposal': True})
    before = path.read_bytes()
    write_once(path, {'bad_proposal': True})
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match='immutable'):
        write_once(path, {'bad_proposal': False})


def test_resume_keeps_bad_result_and_original_cost(tmp_path):
    calls = []
    def invoke():
        calls.append(1)
        return {'status':'format_error', 'text':'broken', 'elapsed_seconds':4.2}
    result = durable_call(tmp_path/'call.json', {'prompt':'x'}, invoke)
    again = durable_call(tmp_path/'call.json', {'prompt':'x'}, lambda: pytest.fail('regenerated bad output'))
    assert result == again and len(calls) == 1
    assert again['elapsed_seconds'] == 4.2
    with pytest.raises(ValueError, match='changed'):
        durable_call(tmp_path/'call.json', {'prompt':'y'}, invoke)


def test_interrupted_call_without_result_blocks(tmp_path):
    path = tmp_path/'call.json'
    def fail():
        raise RuntimeError('interrupted')
    with pytest.raises(RuntimeError): durable_call(path, {'x':1}, fail)
    with pytest.raises(ValueError, match='interrupted'):
        durable_call(path, {'x':1}, lambda: pytest.fail('unapproved repeat'))


def test_raw_result_recovery_does_not_repeat_or_double_charge(tmp_path):
    raw = tmp_path/'raw'
    raw.mkdir()
    path = tmp_path/'call.json'
    def fail():
        write_json_atomic(raw/'completed.json', {'status':'truncated','elapsed_seconds':2.,'request_hash':'bound'})
        raise RuntimeError('crash after persistence')
    with pytest.raises(RuntimeError):
        durable_call(path, {'x':1}, fail, raw_dir=raw, matches=lambda row:row.get('request_hash')=='bound')
    result = durable_call(path, {'x':1}, lambda:pytest.fail('duplicate'), raw_dir=raw,
                          matches=lambda row:row.get('request_hash')=='bound')
    assert result['status']=='truncated' and result['elapsed_seconds']==2.


def test_invalid_natural_proposal_is_retained_without_checks(tmp_path):
    from depverify.pipeline import fake_actor_metadata
    task=load_pilot()[0]
    class Model:
        def generate(self, *args, **kwargs):
                return {'status':'ok','text':'def broken(','elapsed_seconds':1.,'attempt_id':'fake',
                    'input_tokens':5,'output_tokens':3,'timed_out':False}
    class Runner:
        def run(self,*args,**kwargs):pytest.fail('invalid proposal must not execute')
    manifest={'identity':{'revision':'fake','tokenizer_revision':'fake'},'environment':{},
              'check_versions':{c:'v1' for c in ('R1','R2','T','D')},'profile_hash':'a'*64}
    row=collect_episode(task,'natural',tmp_path,Model(),Runner(),manifest,schedule([task])[task.episode_id])
    assert row['proposal']['status']=='syntax_error'
    assert row['checks']=={}
    assert read_json(tmp_path/'private/labels/natural'/f'{task.episode_id}.json')['label']==0
    assert row['proposal']['preflight_seconds']>=0


def test_valid_episode_resume_and_check_inputs_do_not_leak_previous_outcomes(tmp_path):
    from depverify.grading import private_case
    task=load_pilot()[0]
    case=private_case(task)
    prompts=[]
    class Model:
        def generate(self,messages,**kwargs):
            prompts.append(messages)
            text=case['reference'] if kwargs['role']=='proposal' else '{"verdict":"FAIL","reason":"specific evidence"}'
            return {'status':'ok','text':text,'elapsed_seconds':2.,'attempt_id':kwargs['role'],
                    'input_tokens':10,'output_tokens':10,'timed_out':False}
    class Runner:
        calls=[]
        def run(self,files,entry,inputs):
            self.calls.append((files,inputs))
            expected=[t['expected'] for t in task.public_tests] if inputs==[t['input'] for t in task.public_tests] else case['expected']
            return {'status':'ok','outputs':expected,'elapsed_seconds':.4,'container_name':'fake'}
    manifest={'identity':{'revision':'fake','tokenizer_revision':'fake'},'environment':{},
              'check_versions':{c:'v1' for c in ('R1','R2','T','D')},'profile_hash':'a'*64}
    runner=Runner()
    row=collect_episode(task,'natural',tmp_path,Model(),runner,manifest,schedule([task])[task.episode_id])
    assert len(prompts)==4 and len(runner.calls)==2
    for prompt in prompts[1:]:
        assert 'specific evidence' not in canonical_json(prompt).decode()
        assert 'expected' not in canonical_json(prompt).decode()
    assert all(set(files)==set(task.base_files) for files,inputs in runner.calls)
    assert set(row['checks'])=={'R1','R2','T','D'} and 'label' not in row
    again=collect_episode(task,'natural',tmp_path,Model(),runner,manifest,schedule([task])[task.episode_id])
    assert row==again and len(prompts)==4 and len(runner.calls)==2
    write_json_atomic(tmp_path/'episodes/natural'/task.episode_id/'R1.json',{})
    with pytest.raises(ValueError,match='changed'):
        collect_episode(task,'natural',tmp_path,Model(),runner,manifest,schedule([task])[task.episode_id])
