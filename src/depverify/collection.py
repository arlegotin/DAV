"""Bounded M2 collection; public evidence and private labels have separate paths."""
from datetime import datetime, timezone
import fcntl
import itertools
from pathlib import Path
import random
import shutil
import time

from .checks import parse_review
from .local_model import LocalModel, assemble_messages
from .pipeline import (REPO_ROOT, BudgetStop, implementation_hashes, load_config,
                       require_gate, resume_attempts, settle)
from .records import (CHECK_IDS, CheckResult, Proposal, canonical_json, from_dict,
                      parse_json, proposal_key, read_json, sha256_bytes, to_dict, write_json_atomic)
from .runner import ContainerRunner
from .smoke import MemoryMonitor, _limits, forecast_stage, memory_check, validate_prerequisites
from .tasks import load_pilot, materialize, preflight


class CollectionStop(RuntimeError):
    pass


def write_once(path, value):
    path = Path(path)
    if path.exists():
        if canonical_json(read_json(path)) != canonical_json(value):
            raise ValueError('immutable record changed')
        return
    write_json_atomic(path, value)


def eager_ids(tasks):
    return sorted((t.episode_id for t in tasks), key=lambda name:sha256_bytes(name.encode()))[:8]


def schedule(tasks):
    orders = list(itertools.permutations(CHECK_IDS))
    random.Random(7302).shuffle(orders)
    rows = {}
    for index, task in enumerate(sorted(tasks, key=lambda t:t.episode_id)):
        seeds = {action:int(sha256_bytes(f'7303:{task.episode_id}:{action}'.encode())[:8],16)
                 for action in ('actor', *CHECK_IDS, 'eager')}
        rows[task.episode_id] = {'order':list(orders[index % 24]), 'seeds':seeds}
    return rows


def actor_messages(task, system):
    messages = assemble_messages(task, 'proposal')
    if system == 'eager':
        # Add only already allowable documentation before inference. No results/labels.
        prefix = 'Task materials (JSON data):\n'
        body, instruction = messages[-2]['content'][len(prefix):].split('\n\n',1)
        fields = parse_json(body)
        fields['additional_allowed_packets'] = {key:dict(packet) for key,packet in task.source_manifest['packets'].items()
                                                if key != 'A'}
        messages[-2] = {'role':'user','content':prefix+canonical_json(fields).decode()+'\n\n'+instruction}
    elif system != 'natural':
        raise ValueError('unknown pilot system')
    return messages


def lineage(task):
    packets = task.source_manifest['packets']
    a,b = packets['A'],packets['B']
    for packet in (a,b):
        if sha256_bytes(packet['body'].encode()) != packet['sha256']:
            raise ValueError('changed source packet')
    if a['sha256']==b['sha256'] or (a.get('lineage_id') and a.get('lineage_id')==b.get('lineage_id')):
        return 'same_lineage'
    if a.get('lineage_id') and b.get('lineage_id'):
        return 'distinct_lineage'
    return 'unknown_lineage'


def durable_call(path, request, invoke, *, raw_dir=None, matches=None, ledger=None, kind=None):
    """Persist intent before work. A complete bad result is reused as faithfully as PASS."""
    path = Path(path)
    identity = sha256_bytes(canonical_json(request))
    intent = path.with_suffix('.intent.json')
    if path.exists():
        saved = read_json(path)
        if saved['request_hash'] != identity:
            raise ValueError('call inputs changed')
        return saved['result']
    if intent.exists():
        saved = read_json(intent)
        if saved['request_hash'] != identity:
            raise ValueError('interrupted call inputs changed')
        candidates = []
        if raw_dir and matches:
            for raw in Path(raw_dir).glob('*.json'):
                if raw.name not in saved['existing_raw']:
                    row = read_json(raw)
                    if matches(row):candidates.append((raw,row))
        if len(candidates) != 1:
            raise ValueError('interrupted call has no unique complete result; checkpoint for recovery')
        raw,result = candidates[0]
        if ledger:
            reservation = 'reserve:'+kind+'-'+(result.get('attempt_id') or raw.stem)
            settle(ledger,reservation_id=reservation,actual_seconds=result['elapsed_seconds'],status=result['status'])
    else:
        write_once(intent, {'request_hash':identity, 'existing_raw':sorted(p.name for p in Path(raw_dir).glob('*.json')) if raw_dir else []})
        result = invoke()
    write_once(path, {'request_hash':identity,'result':result})
    return result


def require_pilot_gates(run_dir, config_path):
    run_dir = Path(run_dir)
    require_gate(run_dir.parent/'m0/gate.json',stage='M0',expected_hashes=implementation_hashes(config_path))
    m1 = run_dir.parent/'m1'
    inventory = read_json(m1/'input-inventory.json')
    current = {name:sha256_bytes((REPO_ROOT/name).read_bytes()) for name in inventory}
    if current != inventory:
        raise ValueError('M1 runtime inputs changed; a fresh smoke is required')
    identity = read_json(m1/'model-identity.json')
    environment = read_json(m1/'runner-environment.json')
    smoke = read_json(m1/'smoke-results.json')
    expected = {'input_inventory':sha256_bytes(canonical_json(inventory)),
                'model':sha256_bytes(canonical_json(identity)), 'environment':sha256_bytes(canonical_json(environment)),
                'evidence':sha256_bytes(canonical_json(smoke)),
                'config':implementation_hashes(config_path)['config']}
    require_gate(m1/'gate.json',stage='M1',expected_hashes=expected)
    validate_prerequisites(m1)
    return identity,environment,smoke


def _remaining(ledger):
    state = resume_attempts(ledger)
    stage = state['stage_accounted_seconds'].get('M2',{}).get('model',0.)
    return min(3600.-stage,43200.-state['accounted_model_seconds']),state


def _model_call(path, model, messages, role, seed):
    request = {'messages':messages,'role':role,'seed':seed,'temperature':.2 if role=='proposal' else 0}
    def invoke():
        started = time.perf_counter()
        result = model.generate(messages,role=role,seed=seed,temperature=request['temperature'])
        return result | {'call_wall_seconds':time.perf_counter()-started}
    raw_dir = getattr(model,'record_dir',None)
    return durable_call(path,request,invoke,raw_dir=raw_dir,
                        matches=lambda row:row.get('request_hash')==sha256_bytes(canonical_json(request)) and
                        row.get('identity')==getattr(model,'identity',None),
                        ledger=getattr(model,'ledger',None),kind='model')


def _execute(path, runner, task, replacement, inputs):
    files = dict(task.base_files) | {task.editable_path:replacement}
    request = {'files':files,'entry_point':task.entry_point,'inputs':inputs}
    public_hashes = {name:sha256_bytes(body.encode()) for name,body in files.items()}
    payload_hash = sha256_bytes(canonical_json({'entry_point':task.entry_point,'inputs':inputs}))
    return durable_call(path,request,lambda:runner.run(files,task.entry_point,inputs),
                        raw_dir=getattr(runner,'record_dir',None),
                        matches=lambda row:row.get('input_hash')==payload_hash and
                        all(row.get('staged_files',{}).get(name)==digest for name,digest in public_hashes.items()),
                        ledger=getattr(runner,'ledger',None),kind='container')


def _public_check(folder, runner, task, proposal):
    inputs = [test['input'] for test in task.public_tests]
    result = _execute(folder/'T-call.json',runner,task,proposal.replacement,inputs)
    runs = [result]
    if result['status']=='candidate_timeout':
        runs.append(_execute(folder/'T-timeout-confirmation.json',runner,task,proposal.replacement,inputs))
    status = result['status']
    if status == 'ok':
        good = canonical_json(result['outputs']) == canonical_json([test['expected'] for test in task.public_tests])
        verdict = 'PASS' if good else 'FAIL'
    elif status == 'candidate_failure':verdict='FAIL'
    elif status == 'candidate_timeout' and runs[-1]['status']=='candidate_timeout':verdict='FAIL'
    else:
        verdict='UNKNOWN'
        status='infrastructure_error' if status=='candidate_timeout' else status
    return verdict,status,'Fixed public executable tests.',runs


def _grade(folder, runner, task, proposal):
    # Private references/expected outputs are only used on this trusted host.
    from .grading import private_case
    if proposal.status != 'ok':
        unresolved = proposal.status in ('infrastructure_error','model_timeout','interrupted')
        return {'episode_id':task.episode_id,'label':'LABEL_UNRESOLVED' if unresolved else 0,
                'status':proposal.status,'elapsed_seconds':0.}
    case = private_case(task)
    result = _execute(folder/'grade-call.json',runner,task,proposal.replacement,case['inputs'])
    seconds = result['elapsed_seconds']
    if result['status']=='candidate_timeout':
        repeated = _execute(folder/'grade-timeout-confirmation.json',runner,task,proposal.replacement,case['inputs'])
        seconds += repeated['elapsed_seconds']
        if repeated['status']!='candidate_timeout':
            return {'episode_id':task.episode_id,'label':'LABEL_UNRESOLVED','status':'unstable_timeout','elapsed_seconds':seconds}
    if result['status']=='infrastructure_error':label='LABEL_UNRESOLVED'
    elif result['status']=='ok':label=int(canonical_json(result['outputs'])==canonical_json(case['expected']))
    else:label=0
    counterexamples = []
    if result['status']=='ok':
        counterexamples=[{'input':x,'expected':expected,'actual':actual} for x,expected,actual in
                         zip(case['inputs'],case['expected'],result['outputs']) if canonical_json(expected)!=canonical_json(actual)][:3]
    return {'episode_id':task.episode_id,'label':label,'status':result['status'],'elapsed_seconds':seconds,
            'counterexamples':counterexamples}


def collect_episode(task, system, run_dir, model, runner, manifest, row, *, guard=lambda:None):
    run_dir = Path(run_dir)
    folder = run_dir/'episodes'/system/task.episode_id
    complete = folder/'complete.json'
    if complete.exists():
        saved = read_json(complete)
        for name,digest in saved['record_hashes'].items():
            if sha256_bytes((run_dir/name).read_bytes()) != digest:
                raise ValueError('completed episode record changed')
        return read_json(folder/'evidence.json')
    messages = actor_messages(task,system)
    seed = row['seeds']['actor' if system=='natural' else 'eager']
    actor = _model_call(folder/'actor-call.json',model,messages,'proposal',seed)
    guard()
    actor_meta = {key:actor[key] for key in ('input_tokens','output_tokens','timed_out','attempt_id')}
    actor_meta.update(model_revision=manifest['identity']['revision'],tokenizer_revision=manifest['identity']['tokenizer_revision'],
                      seed=seed,prompt_hash=sha256_bytes(canonical_json(messages)),environment_hash=sha256_bytes(canonical_json(manifest['environment'])),
                      elapsed_seconds=actor.get('call_wall_seconds',actor['elapsed_seconds']),cache_hit=False,sampling_settings={'temperature':.2})
    replacement = actor['text']
    root = materialize(task, folder/'disposable')
    try:status,preflight_record=preflight(task,replacement,root)
    finally:shutil.rmtree(root)
    if actor['status'] != 'ok':status=actor['status']
    proposal = Proposal(task.episode_id,proposal_key(task,replacement,manifest['environment'],manifest['check_versions']),
                        replacement,status,actor_meta,preflight_record['elapsed_seconds'])
    proposal_path = folder/'proposal.json'
    if proposal_path.exists():proposal=from_dict(Proposal,read_json(proposal_path))
    else:write_once(proposal_path,to_dict(proposal))
    checks = {}
    order = row['order'] if system=='natural' else ['T']
    if proposal.status=='ok':
        for check in order:
            path = folder/(check+'.json')
            if path.exists():
                checks[check]=from_dict(CheckResult,read_json(path))
                continue
            check_seed = row['seeds'][check]
            if check=='T':
                verdict,status,reason,runs = _public_check(folder,runner,task,proposal)
                elapsed=sum(r['elapsed_seconds'] for r in runs)
                source_hashes={};source_versions={};tokens=(0,0)
                prompt_hash=sha256_bytes(canonical_json(task.public_tests))
                raw_hash=sha256_bytes(canonical_json(runs))
                attempts=[r.get('container_name','fake-container') for r in runs]
                timed_out=any(r['status']=='candidate_timeout' for r in runs)
            else:
                messages=assemble_messages(task,check,proposal.replacement)
                output=_model_call(folder/(check+'-call.json'),model,messages,check,check_seed)
                if output['status'] in ('ok','truncated'):
                    verdict,status,reason=parse_review(output['text'],truncated=output['status']=='truncated')
                else:verdict,status,reason='UNKNOWN',output['status'],''
                elapsed=output.get('call_wall_seconds',output['elapsed_seconds'])
                packet=task.source_manifest['packets'][{'R1':'A','R2':'B','D':'D'}[check]]
                source_hashes={packet['source_id']:packet['sha256']};source_versions={packet['source_id']:packet['version']}
                tokens=(output['input_tokens'],output['output_tokens']);prompt_hash=sha256_bytes(canonical_json(messages))
                raw_hash=sha256_bytes(output['text'].encode());attempts=[output['attempt_id']];timed_out=output['timed_out']
            metadata={'model_revision':manifest['identity']['revision'] if check!='T' else 'none',
                      'tokenizer_revision':manifest['identity']['tokenizer_revision'] if check!='T' else 'none',
                      'check_version':manifest['check_versions'][check],'check_seed':check_seed,'prompt_hash':prompt_hash,
                      'source_hashes':source_hashes,'source_versions':source_versions,'input_tokens':tokens[0],'output_tokens':tokens[1],
                      'timed_out':timed_out,'cache_hit':False,'machine_profile_hash':manifest['profile_hash'],
                      'environment_hash':sha256_bytes(canonical_json(manifest['environment'])),'attempt_ids':attempts,'raw_output_hash':raw_hash}
            result=CheckResult(proposal.proposal_key,check,verdict,status,reason,elapsed,metadata)
            write_once(path,to_dict(result));checks[check]=result
            guard()
    label_path=run_dir/'private/labels'/system/(task.episode_id+'.json')
    if not label_path.exists():write_once(label_path,_grade(run_dir/'private/invocations'/system/task.episode_id,runner,task,proposal))
    evidence={'episode_id':task.episode_id,'root_group_id':task.root_group_id,'split':task.split,'task_class':task.task_class,
              'system':system,'proposal':to_dict(proposal),'lineage':lineage(task),'check_order':order,
              'source_packet_hashes':{key:packet['sha256'] for key,packet in task.source_manifest['packets'].items()},
              'checks':{key:to_dict(result) for key,result in checks.items()}}
    write_once(folder/'evidence.json',evidence)
    paths=[proposal_path,folder/'evidence.json',label_path,*[folder/(check+'.json') for check in checks]]
    write_once(complete,{'record_hashes':{p.relative_to(run_dir).as_posix():sha256_bytes(p.read_bytes()) for p in paths}})
    return evidence


def collect_pilot(run_dir,config_path,*,resume=False,dry_run=False,split='pilot'):
    if split!='pilot':raise ValueError('only M2 pilot is implemented; later splits require their own GO gate')
    run_dir,config_path=Path(run_dir),Path(config_path)
    identity,environment,smoke=require_pilot_gates(run_dir,config_path)
    config=load_config(config_path)
    tasks=load_pilot();rows=schedule(tasks);eager=eager_ids(tasks)
    ledger=run_dir.parent/'work-budget.jsonl'
    remaining,state=_remaining(ledger)
    pending_natural=[t for t in tasks if not (run_dir/'episodes/natural'/t.episode_id/'complete.json').exists()]
    pending_eager=[t for t in tasks if t.episode_id in eager and not (run_dir/'episodes/eager'/t.episode_id/'complete.json').exists()]
    counts={'proposals':len(pending_natural)+int(not (run_dir/'warmup.json').exists()),'reviews':len(pending_natural)*3,
            'eager_proposals':len(pending_eager),'candidate_invocations':2*(len(pending_natural)+len(pending_eager))}
    forecast=forecast_stage(smoke['measurements'],counts,remaining_seconds=remaining)
    plan={'passed':forecast['fits_model_budget'],'required_gate':'M1 GO + current M0 GO','natural_episodes':24,
          'eager_episodes':8,'pending_natural':len(pending_natural),'pending_eager':len(pending_eager),
          'forecast':forecast,'remaining_stage_model_seconds':3600.-state['stage_accounted_seconds'].get('M2',{}).get('model',0.),
          'remaining_total_model_seconds':43200.-state['accounted_model_seconds'],'model_calls_launched':0}
    if dry_run:return plan
    if not plan['passed']:raise BudgetStop('M2 forecast exceeds remaining local budget')
    run_dir.mkdir(parents=True,exist_ok=True)
    with (run_dir/'collection.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:raise CollectionStop('another collection owns the single worker') from exc
        manifest={'schema_version':1,'stage':'M2','identity':identity,'environment':environment,
                  'artifact_hashes':implementation_hashes(config_path),'profile_hash':sha256_bytes(canonical_json(smoke['profile'])),
                  'task_hashes':{t.episode_id:sha256_bytes(canonical_json(to_dict(t))) for t in tasks},
                  'schedule':rows,'eager_task_ids':eager,'warmup_seed':7304,'sampling':{'actor_temperature':.2,'review_temperature':0},
                  'check_versions':{c:sha256_bytes(canonical_json({'adapter':sha256_bytes(Path(__file__).read_bytes()),
                                     'prompt':sha256_bytes((REPO_ROOT/'prompts'/(c+'.txt')).read_bytes()) if c!='T' else 'public-tests',
                                     'model':identity,'environment':environment})) for c in CHECK_IDS}}
        if (run_dir/'frozen-pilot.json').exists() and not resume:
            raise ValueError('existing collection requires --resume; no new candidates')
        write_once(run_dir/'frozen-pilot.json',manifest)
        if not (run_dir/'launch-forecast.json').exists():
            write_once(run_dir/'launch-forecast.json',plan)
        write_json_atomic(run_dir/'current-forecast.json',plan)
        if not pending_natural and not pending_eager:return {'passed':True,'complete':True,'natural_episodes':24,'eager_episodes':8}
        model=LocalModel(identity['path'],identity,ledger,_limits(config),'M2',record_dir=run_dir/'model-calls')
        runner=ContainerRunner(environment['image'],ledger=ledger,limits=_limits(config),stage='M2',record_dir=run_dir/'container-calls')
        monitor=MemoryMonitor(model)
        peak=0
        completed=[]
        def guard():
            nonlocal peak
            if monitor.errors:raise CollectionStop('memory probes failed')
            calls=[read_json(p) for p in sorted((run_dir/'model-calls').glob('*.json'),key=lambda p:p.stat().st_mtime_ns)]
            peak=max([peak,*[c.get('peak_memory_bytes',0) for c in calls]])
            envelope=memory_check(monitor.samples,smoke['profile']['ram_bytes'],peak,environment['engine_memory_bytes'])
            if not envelope['passed']:raise CollectionStop('memory pressure/swap/working-set gate failed')
            slow=0
            for c in calls:
                if c.get('request',{}).get('operation')=='load':continue
                expected=(c['input_tokens']*smoke['measurements']['prompt_seconds_per_token']+
                          c['output_tokens']*smoke['measurements']['generation_seconds_per_token']+
                          smoke['measurements']['call_overhead_seconds'])
                slow=slow+1 if c['elapsed_seconds']>1.5*expected else 0
                if slow>=3:raise CollectionStop('three calls exceeded measured timing by 50%; checkpoint and re-estimate')
        error=None
        try:
            monitor.start();model.start()
            _model_call(run_dir/'warmup.json',model,actor_messages(tasks[0],'natural'),'proposal',7304)
            guard()
            for system,selected in [('natural',tasks),('eager',[t for t in tasks if t.episode_id in eager])]:
                for task in sorted(selected,key=lambda t:t.episode_id):
                    result=collect_episode(task,system,run_dir,model,runner,manifest,rows[task.episode_id],guard=guard)
                    completed.append((system,result['episode_id']))
                    print(f"Collected {system} {task.episode_id}: {result['proposal']['status']}",flush=True)
        except (OSError,ValueError,RuntimeError) as exc:
            error=f'{type(exc).__name__}: {exc}'
        finally:
            model.close();monitor.close()
            checkpoint={'passed':error is None,'complete':error is None,'error':error,'completed_this_session':completed,
                        'memory_samples':monitor.samples,'memory_errors':monitor.errors,'peak_model_bytes':peak,
                        'budget_snapshot':resume_attempts(ledger),'recorded_at':datetime.now(timezone.utc).isoformat()}
            write_json_atomic(run_dir/'checkpoint.json',checkpoint)
        if error:raise CollectionStop(error)
        return {'passed':True,'complete':True,'natural_episodes':24,'eager_episodes':8,'evidence_path':str(run_dir)}
