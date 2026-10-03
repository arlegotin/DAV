"""Verify portable evidence and reproduce pilot decisions without executing code."""
import argparse
import json
from pathlib import Path
import sys

from depverify.collection import CollectionStop
from depverify.evaluate import replay_episode,score_decision,summarize
from depverify.pilot import _load,grouped_difference,screening_policies
from depverify.records import Decision,canonical_json,from_dict,read_json,sha256_bytes

DEFAULT_ARTIFACTS=Path(__file__).resolve().parents[1]/'artifacts/pilots'


def verify_inventory(root):
    root=Path(root).resolve()
    manifest=read_json(root/'manifest.json')
    if manifest.get('schema_version')!=1 or set(manifest.get('panels',{}))!={'original','replacement'}:
        raise ValueError('invalid public inventory schema')
    files=manifest.get('files')
    if not isinstance(files,dict) or not files:raise ValueError('empty public inventory')
    for name,record in files.items():
        path=root/name
        if Path(name).is_absolute() or not path.resolve().is_relative_to(root):
            raise ValueError('inventory path escapes artifact directory')
        if sha256_bytes(path.read_bytes())!=record['sha256']:
            raise ValueError('artifact checksum changed: '+name)
    return manifest


def replay_panel(root,panel):
    directory=panel['directory']
    if Path(directory).name!=directory:raise ValueError('invalid panel path')
    run=Path(root)/directory
    natural=_load(run,'natural',panel['natural_ids'],read_only=True)
    eager=_load(run,'eager',panel['eager_ids'],read_only=True)
    saved_decisions=read_json(run/'replay-decisions.json')
    saved_scores=read_json(run/'replay-scores.json')
    definitions=screening_policies(include_subsets=panel['include_subsets'])
    if set(definitions)!=set(saved_decisions) or set(definitions)!=set(saved_scores):
        raise ValueError('published policy membership differs')
    results={};scores={}
    for name,(policy,definition) in definitions.items():
        policy_hash=sha256_bytes(canonical_json(definition))
        recorded={row['proposal_key']:from_dict(Decision,row) for row in saved_decisions[name]}
        recorded_scores={row['episode_id']:row for row in saved_scores[name]}
        if len(recorded)!=len(natural) or len(recorded_scores)!=len(natural):
            raise ValueError('published episode membership differs')
        rows=[]
        for evidence,proposal,checks,label in natural:
            # The callback sees lineage, availability and acquired verdicts only.
            fresh=replay_episode(proposal,evidence['lineage'],frozenset(checks),policy,checks,policy_hash=policy_hash)
            original=recorded[proposal.proposal_key]
            if (fresh.action,fresh.status,fresh.history,fresh.policy_hash,fresh.selected_check_seconds)!=(
                    original.action,original.status,original.history,original.policy_hash,original.selected_check_seconds):
                raise ValueError('replayed trajectory differs: '+name+'/'+proposal.episode_id)
            # Labels are used after the decision. Retain recorded controller time,
            # rather than substituting this machine's replay or cache-lookup time.
            score=score_decision(proposal,original,label['label'],unit_seconds=panel['unit_seconds'])
            score['root_group_id']=evidence['root_group_id']
            if score!=recorded_scores[proposal.episode_id]:
                raise ValueError('reproduced score differs: '+name+'/'+proposal.episode_id)
            rows.append(score)
        scores[name]=rows;results[name]=summarize(rows)
    eager_counts={'episodes':len(eager),'correct_accepts':0,'incorrect_accepts':0,'deferrals':0}
    policy,definition=screening_policies()['test_only']
    for evidence,proposal,checks,label in eager:
        decision=replay_episode(proposal,evidence['lineage'],frozenset(checks),policy,checks,
                                policy_hash=sha256_bytes(canonical_json(definition)))
        if decision.action=='DEFER':eager_counts['deferrals']+=1
        elif label['label']==1:eager_counts['correct_accepts']+=1
        elif label['label']==0:eager_counts['incorrect_accepts']+=1
        else:raise ValueError('unresolved public label')
    result={'status':panel['status'],'natural_episodes':len(natural),
            'root_groups':len({row[0]['root_group_id'] for row in natural}),
            'verified_policies':len(results),'policies':results,'eager_test_only':eager_counts}
    return result,scores


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts',type=Path,default=DEFAULT_ARTIFACTS)
    parser.add_argument('--json',action='store_true')
    parser.add_argument('--verify-only',action='store_true')
    args=parser.parse_args(argv)
    try:
        manifest=verify_inventory(args.artifacts)
        output={'research_status':manifest['research_status'],'verified_files':len(manifest['files']),
                'model_calls':0,'candidate_executions':0}
        if not args.verify_only:
            output['panels']={}
            for name,panel in manifest['panels'].items():
                result,scores=replay_panel(args.artifacts,panel)
                output['panels'][name]=result
                if name=='replacement':
                    output['replacement_test_minus_defer']=grouped_difference(scores['test_only'],scores['always_defer'])
        if args.json:print(json.dumps(output,sort_keys=True,allow_nan=False))
        else:
            print(f"Recorded research status: {output['research_status']}; verified {output['verified_files']} files.")
            for name,panel in output.get('panels',{}).items():
                print(f"\n{name}: {panel['status']}; {panel['natural_episodes']} natural episodes, {panel['root_groups']} roots.")
                print('Policy                 correct  wrong  defer   mean loss')
                for policy in ('always_accept','always_defer','test_only','single_R1','single_R2','single_D','all_checks_diagnostic'):
                    row=panel['policies'][policy]
                    print(f"{policy:23} {row['correct_accepts']:7} {row['incorrect_accepts']:6} {row['deferrals']:6} {row['mean_loss']:11.3f}")
                print(f"Verified every trajectory and saved score for {panel['verified_policies']} policies.")
            print('\nNo model calls, candidate executions or artifact changes. Pilot results do not authorize a new stage.')
        return 0
    except (OSError,ValueError,KeyError,TypeError,CollectionStop) as exc:
        print('public replay: '+str(exc),file=sys.stderr)
        return 1


if __name__=='__main__':raise SystemExit(main())
