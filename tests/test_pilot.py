from depverify.pilot import screen, screening_policies


def row(i,label,verdicts=None,status='ok',root=None):
    return {'episode_id':str(i),'root_group_id':root or str(i//4),'label':label,'proposal_status':status,
            'verdicts':verdicts or {'R1':'PASS','R2':'PASS','T':'PASS','D':'PASS'}}


def test_unresolved_and_contradictory_public_failure_block():
    rows=[row(i,1) for i in range(24)]
    rows[0]['label']='LABEL_UNRESOLVED'
    assert screen(rows, {}, next_budget_feasible=True)['status']=='BLOCKED'
    rows[0]=row(0,1,{'T':'FAIL','R1':'PASS','R2':'PASS','D':'PASS'})
    assert screen(rows, {}, next_budget_feasible=True)['status']=='BLOCKED'


def test_natural_denominator_includes_malformed_proposals():
    rows=[row(i,i%2,status='syntax_error' if i%2==0 else 'ok') for i in range(24)]
    result=screen(rows, {}, next_budget_feasible=True)
    assert result['counts']=={'attempted':24,'correct':12,'incorrect':12,'unresolved':0,'invalid':12,'valid_incorrect':0}
    assert result['status']=='NO_GO'


def test_one_class_is_inconclusive_without_manufacturing_errors():
    result=screen([row(i,1) for i in range(24)],{},next_budget_feasible=True)
    assert result['status']=='INCONCLUSIVE'
    assert not result['criteria']['two_class_support']


def test_dominant_public_test_has_no_headroom():
    rows=[row(i,i%2,{'T':'PASS' if i%2 else 'FAIL','R1':'PASS','R2':'PASS','D':'PASS'}) for i in range(24)]
    policies={'test_only':{'incorrect_accepts':0,'correct_accepts':12,'mean_loss':3.},
              'single_R1':{'incorrect_accepts':12,'correct_accepts':12,'mean_loss':12.}}
    result=screen(rows,policies,next_budget_feasible=True)
    assert result['status']=='NO_GO' and not result['criteria']['public_test_headroom']


def test_complementary_errors_require_multiple_root_groups_and_economic_headroom():
    rows=[row(i,1) for i in range(12)]
    for i in range(12,24):
        verdicts={c:'PASS' for c in ('R1','R2','T','D')}
        verdicts['T' if i%2 else 'D']='FAIL'
        rows.append(row(i,0,verdicts,root=str(i%3)))
    policies={'test_only':{'incorrect_accepts':6,'correct_accepts':12,'mean_loss':8.},
              'single_D':{'incorrect_accepts':6,'correct_accepts':12,'mean_loss':8.},
              'sequence_T_D_R1_R2':{'incorrect_accepts':0,'correct_accepts':12,'mean_loss':6.}}
    result=screen(rows,policies,next_budget_feasible=True)
    assert result['status']=='GO'
    assert len(result['complementary_root_groups'])>=3
    assert screen(rows,policies,next_budget_feasible=False)['status']=='INCONCLUSIVE'


def test_screening_callbacks_do_not_see_labels_or_full_table():
    policies=screening_policies()
    assert len(policies)==32 # 2 constants + tests + 4 singles + 24 orders + diagnostic
    for name,(policy,definition) in policies.items():
        assert isinstance(definition,dict)
        assert policy('same_lineage',frozenset(('R1','R2','T','D')),(None,None,None,None))[0] in ('R1','R2','T','D','ACCEPT','DEFER')
    policy,_=policies['test_only']
    assert policy('same_lineage',frozenset(('T',)),(None,None,'UNKNOWN',None))[0]=='DEFER'


def test_unresolved_eager_panel_blocks_full_pilot_go(tmp_path,monkeypatch,actor_metadata,check_metadata):
    from pathlib import Path
    import depverify.pilot as p
    from depverify.records import Proposal,CheckResult,write_json_atomic,read_json
    natural=[];eager=[]
    for i in range(24):
        key=f'{i:064x}';name=f'task-{i}'
        proposal=Proposal(name,key,'def solve(x):\n    return x\n','ok',actor_metadata|{'elapsed_seconds':1.},0.)
        checks={c:CheckResult(key,c,'FAIL' if i>=12 and c==('R1' if i%2 else 'D') else 'PASS','ok','specific evidence',
                            1. if c=='R1' else .01,check_metadata) for c in ('R1','R2','T','D')}
        evidence={'episode_id':name,'root_group_id':str(i%3),'lineage':'same_lineage'}
        natural.append((evidence,proposal,checks,{'label':int(i<12)}))
        if i<8:eager.append((evidence,proposal,{'T':checks['T']},{'label':'LABEL_UNRESOLVED'}))
    monkeypatch.setattr(p,'_load',lambda run_dir,system,ids:natural if system=='natural' else eager)
    root=tmp_path/'m2'
    write_json_atomic(root/'frozen-pilot.json',{'task_hashes':{r[0]['episode_id']:'a'*64 for r in natural},'eager_task_ids':[r[0]['episode_id'] for r in eager]})
    write_json_atomic(root/'private/audit.json',{'data_integrity':True,'corrective_evidence_inspected':True})
    write_json_atomic(tmp_path/'m1/smoke-results.json',{'measurements':{'startup_seconds':1.,'prompt_seconds_per_token':.00001,
                     'generation_seconds_per_token':.001,'call_overhead_seconds':.01,'execution_seconds':.1,'timeout_rate':0.}})
    result=p.evaluate_pilot(root,Path('config.toml'))
    assert read_json(root/'analysis.json')['eager_system']['labels_block_stage']
    assert result['status']=='BLOCKED'
