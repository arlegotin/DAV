from depverify.pilot import screen, screening_policies
import pytest


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


def test_paired_difference_matches_episode_identity_not_input_order():
    from depverify.pilot import grouped_difference
    rows=[{'episode_id':str(i),'proposal_key':str(i),'root_group_id':str(i),
           'label_status':'resolved','loss':loss} for i,loss in enumerate((0.,100.))]
    result=grouped_difference(rows,list(reversed(rows)))
    assert result['mean']==0. and result['interval_95']==[0.,0.]


@pytest.mark.parametrize('defect',['missing','duplicate','root','proposal'])
def test_paired_difference_rejects_unmatched_or_conflicting_bindings(defect):
    from depverify.pilot import grouped_difference
    rows=[{'episode_id':str(i),'proposal_key':str(i),'root_group_id':str(i),
           'label_status':'resolved','loss':float(i)} for i in range(2)]
    baseline=[dict(r) for r in rows]
    if defect=='missing':baseline.pop()
    elif defect=='duplicate':baseline[1]=dict(baseline[0])
    elif defect=='root':baseline[0]['root_group_id']='different'
    else:baseline[0]['proposal_key']='different'
    with pytest.raises(ValueError,match='paired'):
        grouped_difference(rows,baseline)


def test_universally_rejecting_review_is_not_complementary_evidence():
    rows=[row(i,int(i<12),{'T':'PASS' if i%2 else 'FAIL','R1':'FAIL','R2':'PASS','D':'PASS'},root=str(i%3))
          for i in range(12,24)]
    rows=[row(i,1,{'T':'PASS','R1':'FAIL','R2':'PASS','D':'PASS'},root=str(i%3)) for i in range(12)]+rows
    policies={'test_only':{'mean_loss':8.},'sequence_T_R1':{'mean_loss':6.}}
    result=screen(rows,policies,next_budget_feasible=True)
    assert not result['criteria']['complementary_checks_three_roots']
    assert not result['criteria']['public_test_headroom']


def test_first_action_bound_does_not_claim_headroom_with_free_later_truth():
    from depverify.pilot import first_action_bound
    rows=[row(0,1,root='a')|{'lineage':'same_lineage','costs':{'T':6.}},
          row(1,0,root='b')|{'lineage':'same_lineage','costs':{'T':6.}}]
    result=first_action_bound(rows,unit_seconds=1.)
    assert result['max_terminal_saving_units']==2.5
    assert result['cheapest_first_action_units']==6.
    assert result['acquisition_loss_lower_bound_vs_defer']==3.5
    assert result['acquisition_can_beat_defer'] is False


def test_prospective_screen_includes_short_sequences_and_requires_audited_evidence():
    policies=screening_policies(include_subsets=True)
    assert len(policies)==68
    assert policies['sequence_T_R2'][0]('same_lineage',frozenset(('T','R2')),(None,None,'PASS',None))[0]=='R2'
    rows=[row(i,1) for i in range(12)]+[row(i,0,{'T':'PASS','R1':'FAIL','R2':'PASS','D':'PASS'}) for i in range(12,24)]
    result=screen(rows,{},next_budget_feasible=True,corrective_ids=set())
    assert not result['criteria']['public_test_headroom']
