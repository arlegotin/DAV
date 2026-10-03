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


def test_critical_baseline_stops_before_model_load(tmp_path,monkeypatch):
    import depverify.collection as c
    monkeypatch.setattr(c,'REPO_ROOT',tmp_path)
    (tmp_path/'prompts').symlink_to(Path('prompts').resolve(),target_is_directory=True)
    identity={'revision':'fake','tokenizer_revision':'fake','path':'fake'}
    smoke={'measurements':{'startup_seconds':1.,'prompt_seconds_per_token':.00001,'generation_seconds_per_token':.001,
                           'call_overhead_seconds':.01,'execution_seconds':.1,'timeout_rate':0.},
           'profile':{'ram_bytes':36*1024**3}}
    environment={'image':'python@sha256:'+'a'*64,'engine_memory_bytes':1024**3}
    monkeypatch.setattr(c,'require_pilot_gates',lambda *args:(identity,environment,smoke))
    calls=[]
    class Model:
        def __init__(self,*args,**kwargs):self.record_dir=None
        def start(self):calls.append('load')
        def generate(self,*args,**kwargs):
            calls.append('generate')
            return {'status':'ok','text':'def solve(x):\n    return x\n','elapsed_seconds':1.,'input_tokens':10,'output_tokens':10,'attempt_id':'fake','timed_out':False}
        def close(self):pass
    class Monitor:
        def __init__(self,*args):
            self.samples=[{'pressure_level':4,'swap_used_bytes':0,'worker_rss_bytes':0,'elapsed_seconds':0.}];self.errors=[]
        def start(self):pass
        def close(self):pass
    monkeypatch.setattr(c,'LocalModel',Model);monkeypatch.setattr(c,'MemoryMonitor',Monitor)
    with pytest.raises(c.CollectionStop,match='memory'):
        c.collect_pilot(tmp_path/'runs/m2',Path('config.toml'))
    assert calls==[]


def test_unconfirmed_cleanup_blocks_cached_and_fresh_invocations(tmp_path):
    from depverify.collection import _execute,CollectionStop
    task=load_pilot()[0]
    class Runner:
        calls=0
        def run(self,*args):
            self.calls+=1
            return {'status':'infrastructure_error','cleanup_ok':False,'container_name':'depverify-unconfirmed',
                    'elapsed_seconds':1.,'outputs':[]}
    path=tmp_path/'T-call.json';runner=Runner()
    with pytest.raises(CollectionStop,match='cleanup'):_execute(path,runner,task,'def solve(x):\n    return x\n',[1])
    assert runner.calls==1
    fresh=Runner()
    with pytest.raises(CollectionStop,match='cleanup'):_execute(path,fresh,task,'def solve(x):\n    return x\n',[1])
    assert fresh.calls==0


def test_retained_cleanup_obligation_blocks_episode_before_actor(tmp_path):
    from depverify.collection import CollectionStop
    task=load_pilot()[0]
    class Model:
        def generate(self,*args,**kwargs):pytest.fail('unsafe resume launched model')
    write_json_atomic(tmp_path/'episodes/natural/earlier/T-call.json',{'result':{'cleanup_ok':False,'status':'infrastructure_error'}})
    with pytest.raises(CollectionStop,match='cleanup'):
        collect_episode(task,'natural',tmp_path,Model(),None,{},schedule([task])[task.episode_id])


def test_resume_guard_amendment_is_bound_and_cannot_change_evidence_inputs(tmp_path):
    from depverify.collection import resume_freeze
    from depverify.records import sha256_bytes
    original={'artifact_hashes':{'code':'a'*64},'check_versions':{'T':'v1'},'schedule':{'seed':1},'identity':{'revision':'same'}}
    current=original|{'artifact_hashes':{'code':'b'*64},'check_versions':{'T':'new-wrapper-sha'}}
    path=tmp_path/'frozen.json';write_once(path,original);before=path.read_bytes()
    with pytest.raises(ValueError,match='amendment'):resume_freeze(path,current)
    amendment={'original_sha256':sha256_bytes(canonical_json(original)),'execution_sha256':sha256_bytes(canonical_json(current)),
               'reason':'reviewed resource/cleanup guards; fixed evidence inputs unchanged'}
    write_json_atomic(tmp_path/'resume-guard-amendment.json',amendment)
    assert resume_freeze(path,current)==original and path.read_bytes()==before
    changed=current|{'schedule':{'seed':2}}
    with pytest.raises(ValueError,match='inputs'):resume_freeze(path,changed)


def test_pending_container_reservation_blocks_before_more_work(tmp_path):
    from depverify.collection import _ensure_cleanup_records, CollectionStop
    from depverify.pipeline import reserve
    ledger = tmp_path/'work-budget.jsonl'
    limits={'total_seconds':{'model':43200.},'stage_seconds':{'M2':{'model':3600.}},
            'per_call_seconds':{'model':180.,'execution':10.}}
    reserve(ledger, attempt_id='container-crash-no-result', stage='M2',
            work_kind='execution', allowance_seconds=10., limits=limits)
    with pytest.raises(CollectionStop, match='pending.*execution'):
        _ensure_cleanup_records(tmp_path/'m2', ledger=ledger)


@pytest.mark.parametrize('completion', [{}, {'record_hashes':{}},
    {'record_hashes':{'../../outside.json':'a'*64}}])
def test_empty_or_out_of_scope_completion_cannot_skip_validation(tmp_path, completion):
    task=load_pilot()[0]
    folder=tmp_path/'episodes/natural'/task.episode_id
    write_json_atomic(folder/'complete.json', completion)
    write_json_atomic(folder/'evidence.json', {'unvalidated':True})
    with pytest.raises(ValueError, match='complet'):
        collect_episode(task,'natural',tmp_path,None,None,{},schedule([task])[task.episode_id])


def test_collection_private_grade_enforces_declared_input_immutability(tmp_path):
    from dataclasses import replace
    from depverify.collection import _grade
    from depverify.grading import private_case
    from depverify.records import Proposal
    from depverify.pipeline import fake_actor_metadata
    task=load_pilot()[0]
    task=replace(task,source_manifest=dict(task.source_manifest)|{'requirements':{'input_immutable':True}})
    case=private_case(task);body='def solve(x):\n    return x\n'
    proposal=Proposal(task.episode_id,'a'*64,body,'ok',fake_actor_metadata(task,body),0.)
    class Runner:
        def run(self,*args):return {'status':'ok','outputs':case['expected'],
            'input_mutated':[True]*len(case['inputs']),'elapsed_seconds':.1}
    assert _grade(tmp_path,Runner(),task,proposal)['label']==0


def test_replacement_collection_refuses_without_original_research_gate(tmp_path):
    from depverify.collection import require_revision
    with pytest.raises(ValueError,match='original.*gate'):
        require_revision(tmp_path/'m2-replacement','interface-v1')


def test_replacement_cannot_be_authorized_by_a_bare_status_file(tmp_path):
    from depverify.collection import require_revision
    write_json_atomic(tmp_path/'m2/gate.json',{'stage':'M2','status':'INCONCLUSIVE'})
    with pytest.raises(ValueError,match='original.*gate'):
        require_revision(tmp_path/'m2-replacement','interface-v1')


def test_alternative_directory_cannot_launch_an_extra_pilot(tmp_path,monkeypatch):
    import depverify.collection as c
    monkeypatch.setattr(c,'REPO_ROOT',tmp_path)
    monkeypatch.setattr(c,'require_pilot_gates',lambda *a,**k:pytest.fail('extra collection reached native gates'))
    with pytest.raises(ValueError,match='fixed.*directory'):
        c.collect_pilot(tmp_path/'runs/another-pilot',Path('config.toml'))
