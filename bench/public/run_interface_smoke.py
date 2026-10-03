"""One fixed public presentation diagnostic, counted in the existing M1 budget."""
from collections import Counter
from pathlib import Path
import uuid

from depverify.checks import parse_review
from depverify.collection import _ensure_cleanup_records, _model_call, write_once
from depverify.local_model import LocalModel, assemble_messages
from depverify.pipeline import implementation_hashes, load_config, require_gate, resume_attempts
from depverify.records import Task, canonical_json, from_dict, read_json, sha256_bytes, write_json_atomic
from depverify.runner import ContainerRunner
from depverify.smoke import MemoryMonitor, _limits, memory_check, validate_prerequisites, forecast_stage


def main():
    root=Path.cwd(); config=root/'config.toml'; run=root/'runs/m1'
    require_gate(root/'runs/m0/gate.json',stage='M0',expected_hashes=implementation_hashes(config))
    validate_prerequisites(run)
    _ensure_cleanup_records(run)
    definition=read_json(root/'bench/public/interface-smoke.json')
    profile=read_json(run/'doctor.json');identity=read_json(run/'model-identity.json')
    environment=read_json(run/'runner-environment.json');ledger=root/'runs/work-budget.jsonl'
    before=resume_attempts(ledger)
    remaining=min(900.-before['stage_accounted_seconds'].get('M1',{}).get('model',0.),43200.-before['accounted_model_seconds'])
    measurements=read_json(run/'smoke-results.json')['measurements']
    forecast=forecast_stage(measurements,{'proposals':1,'reviews':12,'eager_proposals':0,'candidate_invocations':4},remaining_seconds=remaining)
    if not forecast['fits_model_budget']:raise RuntimeError('diagnostic exceeds remaining budget')
    folder=root/'runs/audit-2026-10-03/interface-smoke'/uuid.uuid4().hex
    frozen={'definition':definition,'definition_sha256':sha256_bytes(canonical_json(definition)),
            'hashes':implementation_hashes(config),'identity':identity,'environment':environment,'forecast':forecast}
    write_once(folder/'frozen.json',frozen)
    runner=ContainerRunner(environment['image'],record_dir=folder/'containers',ledger=ledger,
                           limits=_limits(load_config(config)),stage='M1')
    for item in definition['fixtures']:
        task=from_dict(Task,item['task']);inputs=[v['input'] for v in task.public_tests]
        expected=[v['expected'] for v in task.public_tests]
        for truth,key in [(True,'correct_replacement'),(False,'incorrect_replacement')]:
            result=runner.run(dict(task.base_files)|{task.editable_path:item[key]},task.entry_point,inputs)
            actual=result['status']=='ok' and canonical_json(result['outputs'])==canonical_json(expected)
            if result['status']=='infrastructure_error' or result.get('cleanup_ok') is not True or actual!=truth:
                raise RuntimeError('public fixture validation failed')
    model=LocalModel(identity['path'],identity,ledger,_limits(load_config(config)),'M1',record_dir=folder/'model-calls')
    monitor=MemoryMonitor(model);rows=[];calls=[]
    def guard():
        if monitor.errors or not memory_check(monitor.samples,profile['ram_bytes'],
            max((c.get('peak_memory_bytes',0) for c in calls),default=0),environment['engine_memory_bytes'])['passed']:
            raise RuntimeError('memory envelope blocks diagnostic')
    try:
        monitor.start();guard();model.start();guard()
        first=from_dict(Task,definition['fixtures'][0]['task'])
        calls.append(_model_call(folder/'warmup.json',model,assemble_messages(first,'proposal'),'proposal',8499));guard()
        for index,item in enumerate(definition['fixtures']):
            task=from_dict(Task,item['task'])
            for truth,key in [(True,'correct_replacement'),(False,'incorrect_replacement')]:
                for offset,role in enumerate(('R1','R2','D')):
                    guard();seed=8500+index*6+int(truth)*3+offset
                    result=_model_call(folder/(task.episode_id+'-'+key+'-'+role+'.json'),model,
                                       assemble_messages(task,role,item[key]),role,seed)
                    calls.append(result);guard()
                    verdict,status,reason=parse_review(result['text'],truncated=result['status']=='truncated')
                    rows.append({'fixture':task.episode_id,'correct':truth,'check':role,'verdict':verdict,
                                 'status':status,'reason':reason,'call_status':result['status'],'seed':seed})
                    print(task.episode_id,truth,role,verdict,status,flush=True)
    finally:
        model.close();monitor.close()
        write_json_atomic(folder/'partial-results.json',{'rows':rows,'memory':monitor.samples,'errors':monitor.errors})
    valid=sum(r['status']=='ok' and r['call_status']=='ok' for r in rows)
    useful={role:any(r['check']==role and r['correct'] and r['verdict']=='PASS' for r in rows) and
                  any(r['check']==role and not r['correct'] and r['verdict']=='FAIL' for r in rows)
            for role in ('R1','R2','D')}
    result={'passed':len(rows)==12 and valid/12>=.9 and all(useful.values()),'valid_reviews':valid,
            'useful_reviewers':useful,'rows':rows,'budget_before':before,'budget_after':resume_attempts(ledger),
            'scope':definition['role'],'freeze_sha256':sha256_bytes((folder/'frozen.json').read_bytes())}
    write_json_atomic(folder/'results.json',result)
    write_json_atomic(root/'runs/audit-2026-10-03/interface-smoke-result.json',{'path':str(folder/'results.json'),'passed':result['passed']})
    print('INTERFACE_DIAGNOSTIC',result['passed'],folder,flush=True)


if __name__=='__main__':main()
