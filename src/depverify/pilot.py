"""CPU-only M2 screening. Decisions consume masked evidence; labels score afterward."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import itertools
from pathlib import Path
from statistics import median

import numpy as np

from .collection import write_once
from .evaluate import replay_episode, score_decision, summarize
from .pipeline import implementation_hashes, resume_attempts, write_gate
from .records import (CHECK_IDS, EMPTY_HISTORY, CheckResult, GateResult, Proposal, canonical_json,
                      from_dict, read_json, sha256_bytes, to_dict, write_json_atomic)
from .smoke import forecast_stage


def screening_policies():
    """Fixed PASS-only rules, selected on pilot only; not M3 learned baselines."""
    policies={}
    for action in ('ACCEPT','DEFER'):
        policies['always_'+action.lower()] = (lambda g,a,h,action=action:(action,'ok'),{'kind':'constant','action':action})
    def sequence(order,early=True):
        def choose(g,available,history):
            observed=[history[CHECK_IDS.index(c)] for c in order]
            if early and any(v in ('FAIL','UNKNOWN') for v in observed if v is not None):
                return 'DEFER','ok'
            for check in order:
                if check in available and history[CHECK_IDS.index(check)] is None:return check,'ok'
            return ('ACCEPT' if all(history[CHECK_IDS.index(c)]=='PASS' for c in order) else 'DEFER'),'ok'
        return choose
    policies['test_only']=(sequence(('T',)),{'kind':'pass_only','order':['T']})
    for check in CHECK_IDS:policies['single_'+check]=(sequence((check,)),{'kind':'pass_only','order':[check]})
    for order in itertools.permutations(CHECK_IDS):
        policies['sequence_'+'_'.join(order)]=(sequence(order),{'kind':'pass_only','order':list(order),'early_stop':'non-PASS'})
    policies['all_checks_diagnostic']=(sequence(CHECK_IDS,early=False),{'kind':'diagnostic','order':list(CHECK_IDS),'early_stop':'public_FAIL_veto_only'})
    return policies


def screen(rows,policies,*,next_budget_feasible,integrity_passed=True,eager_dominates=False):
    n=len(rows)
    correct=sum(r['label']==1 for r in rows);wrong=sum(r['label']==0 for r in rows)
    unresolved=n-correct-wrong
    invalid=sum(r['proposal_status']!='ok' for r in rows)
    valid_bad=[r for r in rows if r['label']==0 and r['proposal_status']=='ok']
    contradictions=[r['episode_id'] for r in rows if r['label']==1 and
                    (r['proposal_status']!='ok' or r['verdicts'].get('T')=='FAIL')]
    caught={c:{r['episode_id'] for r in valid_bad if r['verdicts'].get(c)=='FAIL'} for c in CHECK_IDS}
    by_id={r['episode_id']:r for r in rows}
    complementary=set()
    pairs=[]
    for a,b in itertools.combinations(CHECK_IDS,2):
        different=caught[a]^caught[b]
        if caught[a] and caught[b] and different:
            roots={by_id[i]['root_group_id'] for i in different}
            complementary.update(roots)
            pairs.append({'checks':[a,b],'different_error_ids':sorted(different),'root_groups':sorted(roots)})
    public_headroom=[r['episode_id'] for r in valid_bad if r['verdicts'].get('T')=='PASS' and
                     any(r['verdicts'].get(c)=='FAIL' for c in ('R1','R2','D'))]
    simple=[v for name,v in policies.items() if name in ('always_accept','always_defer','test_only') or name.startswith('single_')]
    useful_sequences=[]
    for name,result in policies.items():
        if not name.startswith('sequence_') or result.get('mean_loss') is None:continue
        if simple and all(result['mean_loss']<base['mean_loss'] for base in simple):
            useful_sequences.append(name)
    criteria={'two_class_support':correct>=5 and wrong>=5,
              'complementary_checks_three_roots':len(complementary)>=3,
              'public_test_headroom':bool(public_headroom),
              'economic_selection_headroom':bool(useful_sequences),
              'data_integrity':integrity_passed and not contradictions and (not n or unresolved/n<=.02),
              'next_stage_budget':next_budget_feasible,'eager_not_obviously_sufficient':not eager_dominates}
    if not criteria['data_integrity']:status='BLOCKED'
    elif not criteria['two_class_support']:status='INCONCLUSIVE'
    elif invalid and not valid_bad:status='NO_GO'
    elif not all(criteria[k] for k in ('complementary_checks_three_roots','public_test_headroom','economic_selection_headroom','eager_not_obviously_sufficient')):status='NO_GO'
    elif not next_budget_feasible:status='INCONCLUSIVE'
    else:status='GO'
    return {'status':status,'criteria':criteria,'counts':{'attempted':n,'correct':correct,'incorrect':wrong,
            'unresolved':unresolved,'invalid':invalid,'valid_incorrect':len(valid_bad)},
            'caught_error_ids':{c:sorted(ids) for c,ids in caught.items()},'complementary_root_groups':sorted(complementary),
            'complementary_pairs':pairs,'public_pass_corrective_ids':public_headroom,'useful_sequences':useful_sequences,
            'label_contradictions':contradictions,
            'reasons':[name for name,passed in criteria.items() if not passed]}


def _load(run_dir,system,ids):
    rows=[]
    for episode_id in ids:
        folder=run_dir/'episodes'/system/episode_id
        complete=read_json(folder/'complete.json')
        for name,digest in complete['record_hashes'].items():
            if sha256_bytes((run_dir/name).read_bytes())!=digest:raise ValueError('immutable episode changed')
        evidence=read_json(folder/'evidence.json')
        proposal=from_dict(Proposal,evidence['proposal'])
        checks={c:from_dict(CheckResult,value) for c,value in evidence['checks'].items()}
        label=read_json(run_dir/'private/labels'/system/(episode_id+'.json'))
        rows.append((evidence,proposal,checks,label))
    return rows


def grouped_difference(rows,baseline):
    groups=defaultdict(list)
    for row,base in zip(rows,baseline):
        if row['label_status']=='resolved' and base['label_status']=='resolved':
            groups[row['root_group_id']].append(row['loss']-base['loss'])
    if not groups:return None
    means=np.array([np.mean(values) for values in groups.values()])
    samples=np.random.default_rng(7305).choice(means,size=(10000,len(means)),replace=True).mean(axis=1)
    return {'mean':float(means.mean()),'interval_95':np.quantile(samples,[.025,.975]).tolist(),
            'root_groups':len(groups),'resamples':10000,'seed':7305,'role':'exploratory pilot comparison only'}


def evaluate_pilot(run_dir,config_path):
    run_dir=Path(run_dir)
    manifest=read_json(run_dir/'frozen-pilot.json')
    ids=sorted(manifest['task_hashes'])
    natural=_load(run_dir,'natural',ids)
    eager=_load(run_dir,'eager',manifest['eager_task_ids'])
    contradictory=[e['episode_id'] for e,p,checks,label in natural if label['label']==1 and
                   (p.status!='ok' or ('T' in checks and checks['T'].verdict=='FAIL'))]
    if contradictory:
        state=resume_attempts(run_dir.parent/'work-budget.jsonl')
        write_gate(run_dir/'gate.json',GateResult('M2','BLOCKED',datetime.now(timezone.utc).isoformat(),
                   implementation_hashes(config_path),{'public_label_consistency':False},
                   ('Correct label contradicts preflight or public failure: '+', '.join(contradictory),),
                   (str(run_dir/'private/labels'),),state))
        raise ValueError('public failure contradicts private evaluator; repair the benchmark before scoring')
    r1=[checks['R1'].elapsed_seconds for _,_,checks,_ in natural if 'R1' in checks]
    if not r1:raise ValueError('no warm R1 measurement; pilot unit is unresolved')
    unit=median(r1)
    if unit<=0:raise ValueError('pilot R1 cost unit must be positive')
    policies={};scored={};decision_records={}
    for name,(callback,definition) in screening_policies().items():
        policy_hash=sha256_bytes(canonical_json(definition))
        policy_rows=[];decisions=[]
        for evidence,proposal,checks,label in natural:
            decision=replay_episode(proposal,evidence['lineage'],frozenset(checks),callback,checks,policy_hash=policy_hash)
            # Labels are first consulted only after the frozen trajectory terminates.
            score=score_decision(proposal,decision,label['label'],unit_seconds=unit)
            policy_rows.append(score|{'root_group_id':evidence['root_group_id']})
            decisions.append(to_dict(decision))
        policies[name]=summarize(policy_rows);scored[name]=policy_rows;decision_records[name]=decisions
    # Eager grounding is a different actor/system, never a paired verifier ablation.
    callback,definition=screening_policies()['test_only']
    eager_rows=[]
    for evidence,proposal,checks,label in eager:
        decision=replay_episode(proposal,evidence['lineage'],frozenset(checks),callback,checks,
                                policy_hash=sha256_bytes(canonical_json(definition|{'actor':'eager'})))
        eager_rows.append(score_decision(proposal,decision,label['label'],unit_seconds=unit)|{'root_group_id':evidence['root_group_id']})
    frequencies={c:{str(y):dict(Counter(checks[c].verdict for _,_,checks,label in natural if label['label']==y and c in checks))
                      for y in (0,1)} for c in CHECK_IDS}
    statuses={c:dict(Counter(checks[c].status for _,_,checks,_ in natural if c in checks)) for c in CHECK_IDS}
    pairs=Counter((evidence['lineage'],checks['R1'].verdict,checks['R2'].verdict,label['label'])
                  for evidence,_,checks,label in natural if 'R1' in checks and 'R2' in checks)
    inputs=[{'episode_id':e['episode_id'],'root_group_id':e['root_group_id'],'label':l['label'],
             'proposal_status':p.status,'verdicts':{c:r.verdict for c,r in checks.items()}} for e,p,checks,l in natural]
    smoke=read_json(run_dir.parent/'m1/smoke-results.json')
    state=resume_attempts(run_dir.parent/'work-budget.jsonl')
    forecasts={stage:forecast_stage(smoke['measurements'],{'proposals':count+1,'reviews':count*3,'eager_proposals':0,
                 'candidate_invocations':count*2},remaining_seconds=cap) for stage,count,cap in [('M3',144,14400.),('M4',128,10800.)]}
    next_budget=all(f['fits_model_budget'] for f in forecasts.values()) and sum(f['model_seconds_with_margin']+180 for f in forecasts.values())<=43200-state['accounted_model_seconds']
    audit_path=run_dir/'private/audit.json'
    audit=read_json(audit_path) if audit_path.exists() else None
    audit_ok=bool(audit and audit.get('data_integrity') is True and audit.get('corrective_evidence_inspected') is True)
    screening=screen(inputs,policies,next_budget_feasible=next_budget,
                     integrity_passed=not audit or audit.get('data_integrity') is True,
                     eager_dominates=bool(audit and audit.get('eager_obviously_sufficient')))
    if not audit_ok:
        screening['criteria']['trace_audit']=False
        screening['reasons'].append('fixed trace audit pending')
        if screening['status']=='GO':screening['status']='INCONCLUSIVE'
    else:screening['criteria']['trace_audit']=True
    costs={c:[checks[c].elapsed_seconds for _,_,checks,_ in natural if c in checks] for c in CHECK_IDS}
    cost_summary={c:{'count':len(values),'median_seconds':median(values) if values else None,
                     'p95_seconds':float(np.quantile(values,.95)) if values else None} for c,values in costs.items()}
    timeout_counts={c:sum(checks[c].metadata['timed_out'] for _,_,checks,_ in natural if c in checks) for c in CHECK_IDS}
    result={'stage':'M2','status':screening['status'],'pilot_unit_seconds':unit,'screening':screening,
            'policies':policies,'verdict_frequencies_by_label':frequencies,'status_frequencies':statuses,
            'timeout_counts':timeout_counts,'warm_costs':cost_summary,
            'R1_R2_joint':[{'lineage':g,'R1':a,'R2':b,'label':y,'count':n} for (g,a,b,y),n in pairs.items()],
            'eager_system':summarize(eager_rows),'eager_task_ids':manifest['eager_task_ids'],
            'exploratory_differences_vs_tests':{name:grouped_difference(rows,scored['test_only']) for name,rows in scored.items()},
            'forecasts':forecasts,'audit':audit,'budget_snapshot':state,
            'scope':'Development-only screening; no fitted dependency model, no confirmatory or safety claim.'}
    write_json_atomic(run_dir/'analysis.json',result)
    write_json_atomic(run_dir/'replay-decisions.json',decision_records)
    write_json_atomic(run_dir/'replay-scores.json',scored)
    gate=GateResult('M2',screening['status'],datetime.now(timezone.utc).isoformat(),
                    implementation_hashes(config_path)|{'frozen_pilot':sha256_bytes(canonical_json(manifest)),
                    'analysis':sha256_bytes(canonical_json(result))},screening['criteria'],
                    tuple(screening['reasons'] or ['Pilot headroom screening passed; no hypothesis validation yet.']),
                    (str(run_dir/'analysis.json'),str(run_dir/'private/audit.json')),state)
    write_gate(run_dir/'gate.json',gate)
    return {'passed':screening['status']=='GO','status':screening['status'],'counts':screening['counts'],
            'reasons':screening['reasons'],'analysis_path':str(run_dir/'analysis.json')}
