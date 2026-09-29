"""Private host-side evaluator. Policy and model inputs do not import this module."""
from pathlib import Path
from .records import canonical_json, read_json


def private_case(task):
    if task.split != "pilot" or not task.episode_id.startswith("pilot-") or "/" in task.episode_id:
        raise ValueError("only the admitted pilot is available")
    path = Path(__file__).resolve().parents[2] / "bench/private/pilot" / (task.episode_id + ".json")
    case = read_json(path)
    if case["episode_id"] != task.episode_id or canonical_json(case["expected"]) != canonical_json(case["independent_expected"]):
        raise ValueError("private evaluator definitions disagree")
    return case


def grade(task, proposal, runner):
    if proposal.episode_id != task.episode_id:
        raise ValueError("proposal belongs to another task")
    if proposal.status != "ok":
        return {"episode_id": task.episode_id, "label": 0, "status": proposal.status, "elapsed_seconds": 0.}
    case = private_case(task)
    result = runner.run(dict(task.base_files) | {task.editable_path: proposal.replacement}, task.entry_point, case["inputs"])
    if result["status"] == "infrastructure_error":
        label = "LABEL_UNRESOLVED"
    elif result["status"] == "ok":
        label = int(canonical_json(result["outputs"]) == canonical_json(case["expected"]))
    else:
        label = 0
    return {"episode_id": task.episode_id, "label": label, "status": result["status"],
            "elapsed_seconds": result["elapsed_seconds"]}


def validate_pilot(runner):
    from .tasks import load_pilot
    rows = []
    for task in load_pilot():
        case = private_case(task)
        runs = {}
        # Public and hidden invocations are separate; expected outputs stay here.
        for name, body in {"reference": case["reference"], "original": task.base_files[task.editable_path],
                           **case["mutants"]}.items():
            result = runner.run(dict(task.base_files) | {task.editable_path: body}, task.entry_point, case["inputs"])
            good = result["status"] == "ok" and canonical_json(result["outputs"]) == canonical_json(case["expected"])
            runs[name] = {"status": result["status"], "passes": good, "seconds": result["elapsed_seconds"]}
        public = runner.run(dict(task.base_files) | {task.editable_path: case["reference"]}, task.entry_point,
                            [test["input"] for test in task.public_tests])
        public_ok = public["status"] == "ok" and canonical_json(public["outputs"]) == canonical_json([test["expected"] for test in task.public_tests])
        passed = (runs["reference"]["passes"] and public_ok and
                  all(not row["passes"] and row["status"] != "infrastructure_error" for name, row in runs.items() if name != "reference"))
        rows.append({"episode_id": task.episode_id, "passed": passed, "runs": runs, "public_reference_passed": public_ok})
    return {"passed": all(row["passed"] for row in rows), "tasks": rows,
            "note": "References/mutations validate the evaluator; none are natural model proposals."}
