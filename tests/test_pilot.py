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
