"""Private host-side evaluator. Policy and model inputs do not import this module."""
from pathlib import Path
from .records import canonical_json, read_json


def private_case(task):
    if task.split != "pilot" or not task.episode_id.startswith(("pilot-","replacement-")) or "/" in task.episode_id:
        raise ValueError("only the admitted pilot is available")
    stem='replacement-pilot' if task.episode_id.startswith('replacement-') else 'pilot'
    path = Path(__file__).resolve().parents[2] / "bench/private" / stem / (task.episode_id + ".json")
    case = read_json(path)
    if case["episode_id"] != task.episode_id or canonical_json(case["expected"]) != canonical_json(case["independent_expected"]):
        raise ValueError("private evaluator definitions disagree")
    return case


def grade(task, proposal, runner):
    if proposal.episode_id != task.episode_id:
        raise ValueError("proposal belongs to another task")
    if proposal.status != "ok":
        label='LABEL_UNRESOLVED' if proposal.status in ('infrastructure_error','model_timeout','interrupted') else 0
        return {"episode_id": task.episode_id, "label": label, "status": proposal.status, "elapsed_seconds": 0.}
    case = private_case(task)
    result = runner.run(dict(task.base_files) | {task.editable_path: proposal.replacement}, task.entry_point, case["inputs"])
    runs=[result]
    if result['status']=='candidate_timeout':
        runs.append(runner.run(dict(task.base_files)|{task.editable_path:proposal.replacement},task.entry_point,case['inputs']))
    if result["status"] == "infrastructure_error":
        label = "LABEL_UNRESOLVED"
    elif result["status"] == "ok":
        label = int(execution_matches(task,result,case['expected']))
    elif result['status']=='candidate_timeout' and runs[-1]['status']!='candidate_timeout':
        label='LABEL_UNRESOLVED'
    else:
        label = 0
    return {"episode_id": task.episode_id, "label": label, "status": result["status"],
            "elapsed_seconds": sum(r['elapsed_seconds'] for r in runs)}


def execution_matches(task,result,expected):
    if result['status']!='ok':return False
    if task.source_manifest.get('requirements',{}).get('input_immutable') is True:
        flags=result.get('input_mutated')
        if (not isinstance(flags,list) or len(flags)!=len(expected) or
                any(type(flag) is not bool for flag in flags)):
            raise ValueError('required input mutation observations unavailable')
        if any(flags):return False
    return canonical_json(result['outputs'])==canonical_json(expected)


def validate_pilot(runner, *,tasks=None):
    from .tasks import load_pilot
    rows = []
    for task in (load_pilot() if tasks is None else tasks):
        case = private_case(task)
        runs = {}
        # Public and hidden invocations are separate; expected outputs stay here.
        for name, body in {"reference": case["reference"], "original": task.base_files[task.editable_path],
                           **case["mutants"]}.items():
            result = runner.run(dict(task.base_files) | {task.editable_path: body}, task.entry_point, case["inputs"])
            good = execution_matches(task,result,case['expected'])
            runs[name] = {"status": result["status"], "passes": good, "seconds": result["elapsed_seconds"]}
        public = runner.run(dict(task.base_files) | {task.editable_path: case["reference"]}, task.entry_point,
                            [test["input"] for test in task.public_tests])
        public_ok = execution_matches(task,public,[test['expected'] for test in task.public_tests])
        passed = (runs["reference"]["passes"] and public_ok and
                  all(not row["passes"] and row["status"] != "infrastructure_error" for name, row in runs.items() if name != "reference"))
        rows.append({"episode_id": task.episode_id, "passed": passed, "runs": runs, "public_reference_passed": public_ok})
    from .smoke import prerequisite_bindings
    return {"passed": all(row["passed"] for row in rows), "tasks": rows, "bindings":prerequisite_bindings(runner.image),
            "note": "References/mutations validate the evaluator; none are natural model proposals."}
