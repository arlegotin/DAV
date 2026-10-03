"""Trusted masked replay; private scoring is performed after decisions."""

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import itertools
import math
from pathlib import Path
from statistics import mean
import tempfile
import time
import uuid

import numpy as np

from .records import CHECK_IDS, EMPTY_HISTORY, LINEAGES, VERDICTS, CheckResult, Decision, Proposal, Task, append_event, canonical_json, read_json, sha256_bytes, to_dict, write_json_atomic


def replay_episode(proposal: Proposal, lineage: str, available: frozenset[str], policy: Callable,
                   evidence: Mapping[str, CheckResult], *, policy_hash: str) -> Decision:
    started = time.perf_counter()
    history, acquired, selected_seconds = [None] * 4, [], 0.

    def finish(action, status):
        return Decision(proposal.proposal_key, policy_hash, tuple(acquired), action, status,
                        selected_seconds, time.perf_counter() - started, 0.)

    if proposal.status != "ok":
        return finish("DEFER", "invalid_proposal")
    if not isinstance(available, frozenset) or not available.issubset(CHECK_IDS):
        return finish("DEFER", "invalid_availability")

    def request(check_id: str) -> str:
        nonlocal selected_seconds
        if check_id not in available:
            raise ValueError("unavailable_request")
        index = CHECK_IDS.index(check_id)
        if history[index] is not None:
            raise ValueError("duplicate_request")
        try:
            result = evidence[check_id]
        except KeyError as exc:
            raise ValueError("missing_evidence") from exc
        if not isinstance(result, CheckResult):
            raise ValueError("invalid_evidence")
        if result.proposal_key != proposal.proposal_key or result.check_id != check_id:
            raise ValueError("stale_evidence")
        selected_seconds += result.elapsed_seconds
        acquired.append((check_id, result.verdict))
        history[index] = result.verdict
        return result.verdict

    for _ in range(5):
        if history[2] == "FAIL":
            return finish("DEFER", "public_fail_veto")
        try:
            choice = policy(lineage, available, tuple(history))
        except Exception:
            return finish("DEFER", "policy_error")
        if not isinstance(choice, tuple) or len(choice) != 2 or not all(isinstance(v, str) and v for v in choice):
            return finish("DEFER", "invalid_policy_output")
        action, status = choice
        if action == "DEFER":
            return finish(action, status)
        if status != "ok":
            return finish("DEFER", status)
        if action == "ACCEPT":
            return finish(action, status)
        if action not in CHECK_IDS:
            return finish("DEFER", "invalid_policy_output")
        try:
            request(action)
        except ValueError as exc:
            return finish("DEFER", str(exc))
    return finish("DEFER", "acquisition_limit")


def _nonnegative(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return float(value)


def score_decision(proposal: Proposal, decision: Decision, label: int | str, *, unit_seconds: float,
                   wrong_accept: float = 20., defer: float = 5.) -> dict:
    unit = _nonnegative(unit_seconds, "unit")
    if unit == 0.:
        raise ValueError("unit must be positive")
    wrong, deferred_cost = _nonnegative(wrong_accept, "wrong_accept"), _nonnegative(defer, "defer")
    if decision.proposal_key != proposal.proposal_key:
        raise ValueError("decision does not match frozen proposal")
    unresolved = label == "LABEL_UNRESOLVED"
    if not unresolved and (type(label) is not int or label not in (0, 1)):
        raise ValueError("unknown correctness label")
    if label == 1 and (proposal.status != "ok" or ("T", "FAIL") in decision.history):
        raise ValueError("correct label contradicts mechanical or public failure")
    times = {"actor_seconds": proposal.actor["elapsed_seconds"], "preflight_seconds": proposal.preflight_seconds,
             "selected_check_seconds": decision.selected_check_seconds, "controller_seconds": decision.controller_seconds,
             "wrapper_seconds": decision.wrapper_seconds}
    total = sum(times.values())
    normalized = _nonnegative(total / unit, "normalized_work")
    accepted, deferral = decision.action == "ACCEPT", int(decision.action == "DEFER")
    correct = None if unresolved else int(accepted and label == 1)
    incorrect = None if unresolved else int(accepted and label == 0)
    loss = None if unresolved else _nonnegative(normalized + wrong * incorrect + deferred_cost * deferral, "loss")
    counts = dict.fromkeys(CHECK_IDS, 0)
    for check, _ in decision.history:
        counts[check] += 1
    return {"episode_id": proposal.episode_id, "proposal_key": proposal.proposal_key, "policy_hash": decision.policy_hash,
            "action": decision.action, "decision_status": decision.status, "label": label,
            "label_status": "unresolved" if unresolved else "resolved", "correct_accept": correct,
            "incorrect_accept": incorrect, "deferral": deferral, "loss": loss, "normalized_work": normalized,
            "total_seconds": total, "verification_seconds": decision.selected_check_seconds + decision.controller_seconds,
            "acquired_checks": len(decision.history), "check_counts": counts,
            "unknown_count": sum(verdict == "UNKNOWN" for _, verdict in decision.history), **times}


def summarize(rows) -> dict:
    rows = list(rows)
    if len({row["episode_id"] for row in rows}) != len(rows):
        raise ValueError("duplicate proposal episodes cannot inflate sample size")
    if len({row["policy_hash"] for row in rows}) > 1:
        raise ValueError("summarize one policy at a time")
    if any(not isinstance(row.get("root_group_id"), str) or not row["root_group_id"] for row in rows):
        raise ValueError("explicit root groups are required")
    eligible = [row for row in rows if row["label_status"] == "resolved"]
    groups = {}
    for row in eligible:
        groups.setdefault(row["root_group_id"], []).append(row)
    def grouped_average(column):
        return mean(mean(row[column] for row in group) for group in groups.values()) if groups else None
    correct = sum(row["correct_accept"] for row in eligible)
    incorrect = sum(row["incorrect_accept"] for row in eligible)
    acquired = sum(row["acquired_checks"] for row in eligible)
    mean_time, mean_correct = grouped_average("total_seconds"), grouped_average("correct_accept")
    efficiency = mean_time / mean_correct if mean_correct else None
    unresolved = len(rows) - len(eligible)
    accepted = correct + incorrect
    return {"episodes": len(rows), "root_groups": len({row["root_group_id"] for row in rows}),
            "analyzed_episodes": len(eligible), "analyzed_root_groups": len(groups), "unresolved_labels": unresolved,
            "labels_block_stage": bool(rows) and unresolved / len(rows) > .02,
            "correct_accepts": correct, "incorrect_accepts": incorrect,
            "deferrals": sum(row["deferral"] for row in eligible), "all_attempt_deferrals": sum(row["deferral"] for row in rows),
            "correct_accepts_per_attempt": mean_correct,
            "incorrect_accepts_per_attempt": grouped_average("incorrect_accept"),
            "incorrect_among_accepted": (grouped_average("incorrect_accept") /
                (mean_correct+grouped_average("incorrect_accept"))) if accepted else None,
            "raw_correct_accepts_per_attempt": correct / len(rows) if rows else None,
            "raw_incorrect_accepts_per_attempt": incorrect / len(rows) if rows else None,
            "raw_incorrect_among_accepted": incorrect / accepted if accepted else None,
            "rate_estimand": "equal weight per analyzed root group; unresolved labels excluded explicitly",
            "mean_loss": grouped_average("loss"), "mean_total_seconds": mean_time,
            "total_seconds": sum(row["total_seconds"] for row in rows),
            "verification_seconds": sum(row["verification_seconds"] for row in rows),
            "seconds_per_correct_accept": efficiency,
            "efficiency_status": "estimable" if efficiency is not None else "undefined_no_correct_accepts",
            "mean_acquired_checks": grouped_average("acquired_checks"),
            "mean_checks_by_id": {check: mean(mean(row["check_counts"][check] for row in group) for group in groups.values())
                                  if groups else None for check in CHECK_IDS},
            "unknown_rate": sum(row["unknown_count"] for row in eligible) / acquired if acquired else None,
            "denominator_ledger": {"intended": len(rows), "analyzed": len(eligible), "unresolved": unresolved}}


def _toy(kind, prior=.5):
    table = np.zeros((2, 3, 3, 3, 3))
    if kind == "constant":
        table[0, 2, 2, 2, 2], table[1, 2, 2, 2, 2] = 1. - prior, prior
    elif kind == "copied":
        for cell, mass in [((1, 0, 0, 2, 2), .4), ((1, 1, 1, 2, 2), .1), ((0, 0, 0, 2, 2), .1), ((0, 1, 1, 2, 2), .4)]:
            table[cell] = mass
    elif kind == "xor":
        for y, a, b in [(1, 0, 0), (1, 1, 1), (0, 0, 1), (0, 1, 0)]:
            table[y, a, b, 2, 2] = .25
    elif kind == "independent_pair":
        for y, a, b in itertools.product(range(2), repeat=3):
            table[y, a, b, 2, 2] = .125
    elif kind in ("perfect", "perfect_test"):
        index = 0 if kind == "perfect" else 2
        for y in (0, 1):
            vector = [2] * 4
            vector[index] = 0 if y == 1 else 1
            table[(y, *vector)] = .5
    elif kind == "asymmetric":
        table[1, 0, 2, 2, 2], table[1, 2, 2, 2, 2] = .4, .1
        table[0, 0, 2, 2, 2], table[0, 1, 2, 2, 2] = .05, .45
    elif kind == "independent":
        singles = [((.2, .7, .1), (.3, .6, .1), (.2, .7, .1), (.1, .8, .1)),
                   ((.8, .1, .1), (.7, .2, .1), (1., 0., 0.), (.9, .05, .05))]
        for y, vector in itertools.product(range(2), itertools.product(range(3), repeat=4)):
            table[(y, *vector)] = .5 * math.prod(singles[y][j][o] for j, o in enumerate(vector))
    else:
        raise ValueError("unknown toy world")
    return table


def _exhaustive_value(table, policy, available, costs):
    result = 0.
    for y, vector in itertools.product(range(2), itertools.product(range(3), repeat=4)):
        mass = float(table[(y, *vector)])
        if mass == 0.:
            continue
        history, work = [None] * 4, 0.
        for _ in range(5):
            action, _ = policy("same_lineage", available, tuple(history))
            if action in ("ACCEPT", "DEFER"):
                work += 20. * (action == "ACCEPT" and y == 0) + 5. * (action == "DEFER")
                break
            index = CHECK_IDS.index(action)
            if action not in available or history[index] is not None:
                raise ValueError("invalid exhaustive trajectory")
            work += costs[action]
            history[index] = VERDICTS[vector[index]]
        else:
            raise ValueError("nonterminating exhaustive trajectory")
        result += mass * work
    return result


def _same(expected, actual):
    if isinstance(expected, bool):
        return expected is actual
    if isinstance(expected, (float, int)) and isinstance(actual, (float, int)):
        return math.isclose(expected, actual, rel_tol=0., abs_tol=1e-12)
    if isinstance(expected, (tuple, list)) and isinstance(actual, (tuple, list)):
        return len(expected) == len(actual) and all(_same(e, a) for e, a in zip(expected, actual))
    return expected == actual


def _fake_flow(attempt):
    from .checks import fake_check
    from .pipeline import FAKE_CHECK_VERSIONS, FAKE_ENVIRONMENT, fake_actor_metadata, run_fake_episode
    from .policy import test_only
    from .records import proposal_key
    from .runner import FakeRunner
    rows, originals_unchanged = [], True
    with tempfile.TemporaryDirectory(prefix="files-", dir=attempt) as directory:
        for index, replacement in enumerate(("def solve(x):\n    return x\n", "def solve(x):\n    return None\n", "def solve(:\n")):
            task = Task(f"fake-{index}", f"fake-root-{index}", "fake", "fake", "Return the input JSON value.", "candidate.py", "solve",
                        {"candidate.py": "def solve(x):\n    return None\n", "support.py": "VERSION = 1\n"},
                        ({"input": 2, "expected": 2},), {"A": {"lineage_id": "fake-manual", "version": "1", "body": "Return x."}})
            original = canonical_json(to_dict(task))
            key = proposal_key(task, replacement, FAKE_ENVIRONMENT, FAKE_CHECK_VERSIONS)
            frozen = Proposal(task.episode_id, key, replacement, "ok", fake_actor_metadata(task, replacement), 0.)
            evidence = {}
            if index < 2:
                outputs = [2] if index == 0 else [None]
                execution = FakeRunner({key: {"inputs": [2], "outputs": outputs, "status": "ok", "elapsed_seconds": .2}}).run(key, [2])
                verdict = "PASS" if execution["outputs"] == [2] else "FAIL"
                for check, seconds in [("R1", 12.), ("R2", 3.), ("T", .2), ("D", 10.)]:
                    metadata = {"check_version": "fake-v1", "model_revision": "fake-v1", "tokenizer_revision": "fake-v1", "check_seed": CHECK_IDS.index(check) + 2,
                                "prompt_hash": sha256_bytes(check.encode()), "source_hashes": {}, "source_versions": {},
                                "input_tokens": 10, "output_tokens": 5, "timed_out": False, "cache_hit": False,
                                "machine_profile_hash": sha256_bytes(b"fake"), "environment_hash": sha256_bytes(canonical_json(FAKE_ENVIRONMENT)),
                                "attempt_ids": ["fake:" + task.episode_id + ":" + check], "sampling_settings": {"temperature": 0}, "cost_regime": "synthetic"}
                    raw = canonical_json({"verdict": verdict, "reason": "Fixed fake fixture."}).decode()
                    evidence[check] = fake_check(frozen, check, {"raw": raw, "verdict": verdict, "elapsed_seconds": seconds, "metadata": metadata})
                    append_event(attempt / "checks.jsonl", {"event_id": task.episode_id + ":" + check, "record": to_dict(evidence[check])})
            proposal, decision = run_fake_episode(task, replacement, evidence, test_only, Path(directory))
            label = 1 if index == 0 else 0
            append_event(attempt / "proposals.jsonl", {"event_id": task.episode_id, "record": to_dict(proposal)})
            append_event(attempt / "decisions.jsonl", {"event_id": task.episode_id, "record": to_dict(decision)})
            append_event(attempt / "private/labels.jsonl", {"event_id": task.episode_id, "episode_id": task.episode_id, "Y": label, "scope": "fake_fixture"})
            rows.append(score_decision(proposal, decision, label, unit_seconds=2.) | {"root_group_id": task.root_group_id})
            originals_unchanged = originals_unchanged and canonical_json(to_dict(task)) == original
        files = list(Path(directory).glob(".depverify-*"))
        changed = sorted((file / "candidate.py").read_text() for file in files)
        permissions = originals_unchanged and changed.count("def solve(x):\n    return x\n") == 1 and changed.count("def solve(x):\n    return None\n") == 2
    return summarize(rows), bool(permissions)


def run_core_suite(run_dir: Path) -> dict:
    from .pipeline import FAKE_CHECK_VERSIONS, FAKE_ENVIRONMENT, fake_actor_metadata, implementation_hashes, resume_attempts
    from .policy import make_policy, plan
    from .probability import posterior_correct, predictive, save_tables
    started = time.perf_counter()
    root = Path(run_dir)
    attempt_path = Path("attempts") / uuid.uuid4().hex
    attempt = root / attempt_path
    attempt.mkdir(parents=True, exist_ok=False)
    controls = []
    def check(identifier, expected, function):
        try:
            actual = function()
            passed = bool(_same(expected, actual))
        except Exception as exc:
            actual, passed = {"error": type(exc).__name__, "message": str(exc)}, False
        controls.append({"id": identifier, "passed": passed, "expected": expected, "actual": actual})
    all_actions, costs = frozenset(CHECK_IDS), {"R1": .1, "R2": .2, "T": .05, "D": .3}
    independent, copied, constant, xor, singleton = (_toy(k) for k in ("independent", "copied", "constant", "xor", "perfect"))
    check("independent_checks", 0., lambda: plan(independent, EMPTY_HISTORY, all_actions, costs)[1] - _exhaustive_value(independent, make_policy({g: independent for g in LINEAGES}, costs), all_actions, costs))
    check("copied_checks", [.8, .8], lambda: [posterior_correct(copied, ("PASS", None, None, None)), posterior_correct(copied, ("PASS", "PASS", None, None))])
    check("mixed_modalities", True, lambda: bool(0. < plan(independent, EMPTY_HISTORY, all_actions, costs)[1] < 5.))
    check("all_useless", ["DEFER", 5.], lambda: list(plan(constant, EMPTY_HISTORY, all_actions, costs)))
    check("free_perfect", ["R1", 2.5], lambda: list(plan(singleton, EMPTY_HISTORY, frozenset({"R1"}), {"R1": 0.})))
    check("expensive_perfect", ["DEFER", 5.], lambda: list(plan(singleton, EMPTY_HISTORY, frozenset({"R1"}), {"R1": 3.})))
    check("asymmetric_failure", ["R1", 3.35], lambda: list(plan(_toy("asymmetric"), EMPTY_HISTORY, frozenset({"R1"}), {"R1": .1})))
    check("xor_complementarity", ["R1", 2.7], lambda: list(plan(xor, EMPTY_HISTORY, frozenset({"R1", "R2"}), {"R1": .1, "R2": .1})))
    check("zero_unknown_support", ["DEFER", "zero_support"], lambda: list(make_policy({g: constant for g in LINEAGES}, costs)("same_lineage", all_actions, ("PASS", None, None, None))))
    check("missing_actions", ["DEFER", 5.], lambda: list(plan(singleton, EMPTY_HISTORY, frozenset(), {})))
    check("all_unknown", ["DEFER", 5.], lambda: list(plan(constant, ("UNKNOWN",) * 4, all_actions, costs)))
    check("zero_cost", ["DEFER", 5.], lambda: list(plan(constant, EMPTY_HISTORY, all_actions, dict.fromkeys(CHECK_IDS, 0.))))
    check("public_fail_veto", ["DEFER", 5.], lambda: list(plan(constant, (None, None, "FAIL", None), all_actions, costs)))
    check("dominant_cheap_test", ["T", 2.51], lambda: list(plan(_toy("perfect_test"), EMPTY_HISTORY, all_actions, {"R1": .1, "R2": .1, "T": .01, "D": .1})))
    check("normalization", 1., lambda: float(independent.sum()))
    def total_probability():
        prediction = predictive(independent, EMPTY_HISTORY, "R1")
        return sum(float(probability) * posterior_correct(independent, (verdict, None, None, None)) for probability, verdict in zip(prediction, VERDICTS) if probability)
    check("total_probability", .5, total_probability)
    for price, name, expected in [(.1, "coupling_gain", [2.7, 5.]), (3., "coupling_no_gain", [5., 5.])]:
        def values(price=price):
            menu, prices = frozenset({"R1", "R2"}), {"R1": price, "R2": price}
            return [_exhaustive_value(xor, make_policy({g: table for g in LINEAGES}, prices), menu, prices) for table in (xor, _toy("independent_pair"))]
        check(name, expected, values)
    def histories():
        callback, count = make_policy({g: independent for g in LINEAGES}, costs), 0
        for history in itertools.product((None, *VERDICTS), repeat=4):
            for mask in range(16):
                available = frozenset(c for i, c in enumerate(CHECK_IDS) if mask & (1 << i))
                current = list(history)
                for _ in range(5):
                    action, _ = callback("same_lineage", available, tuple(current))
                    if action in ("ACCEPT", "DEFER"):
                        break
                    index = CHECK_IDS.index(action)
                    if current[index] is not None or action not in available:
                        raise ValueError("invalid history transition")
                    current[index] = "UNKNOWN"
                else:
                    raise ValueError("nontermination")
                count += 1
        return count
    check("finite_histories", 4096, histories)
    metadata = {"check_version": "fake-v1", "model_revision": "fake-v1", "tokenizer_revision": "fake-v1", "check_seed": 2,
                "prompt_hash": "a" * 64, "source_hashes": {}, "source_versions": {}, "input_tokens": 10, "output_tokens": 5,
                "timed_out": False, "cache_hit": True, "machine_profile_hash": "b" * 64, "environment_hash": "c" * 64, "attempt_ids": ["fake"], "cost_regime": "synthetic"}
    task = Task("fake-replay", "fake-root", "fake", "fake", "Return x.", "candidate.py", "solve", {"candidate.py": "def solve(x): return x"}, (), {})
    proposal = Proposal(task.episode_id, "1" * 64, "def solve(x): return x", "ok", fake_actor_metadata(task, ""), 0.)
    evidence = {c: CheckResult("1" * 64, c, "PASS", "ok", "", 12. if c == "R1" else 3., metadata) for c in CHECK_IDS}
    def one_review(lineage, available, history):
        return ("R1", "ok") if history[0] is None else ("ACCEPT", "ok")
    def signature(record):
        return [record.action, list(map(list, record.history)), record.selected_check_seconds]
    def altered():
        before = signature(replay_episode(proposal, "same_lineage", all_actions, one_review, evidence, policy_hash="2" * 64))
        for c in ("R2", "T", "D"):
            changed = evidence | {c: CheckResult("1" * 64, c, "FAIL", "ok", "different", 99., metadata)}
            if signature(replay_episode(proposal, "same_lineage", all_actions, one_review, changed, policy_hash="2" * 64)) != before:
                return False
        return True
    check("altered_unrequested", True, altered)
    check("hidden_labels", True, lambda: len({canonical_json(signature(replay_episode(proposal, "same_lineage", all_actions, one_review, evidence, policy_hash="2" * 64))) for private_label in (0, 1, "LABEL_UNRESOLVED")}) == 1)
    def duplicate():
        decision = replay_episode(proposal, "same_lineage", all_actions, lambda *args: ("R1", "ok"), evidence, policy_hash="2" * 64)
        return [decision.action, decision.status, decision.selected_check_seconds, len(decision.history)]
    check("duplicate_request", ["DEFER", "duplicate_request", 12., 1], duplicate)
    def accounting():
        proposal2 = Proposal(task.episode_id, "1" * 64, proposal.replacement, "ok", proposal.actor, 2.)
        decision = Decision("1" * 64, "2" * 64, (("R1", "PASS"),), "ACCEPT", "ok", 4., 1., 1.)
        return [score_decision(proposal2, decision, 1, unit_seconds=2.)["loss"], score_decision(proposal2, decision, 0, unit_seconds=2.)["loss"]]
    check("cost_accounting", [8., 28.], accounting)
    try:
        workflow, permissions = _fake_flow(attempt)
        check("temporary_permissions", True, lambda: permissions)
        check("accept_defer_flow", [1, 0, 2, 3], lambda: [workflow["correct_accepts"], workflow["incorrect_accepts"], workflow["deferrals"], workflow["episodes"]])
    except Exception as exc:
        workflow = {"error": type(exc).__name__, "message": str(exc)}
        check("temporary_permissions", True, lambda: False)
        check("accept_defer_flow", True, lambda: False)
    save_tables(attempt / "toy_tables.json", {g: copied for g in LINEAGES}, model_version="m0-toy-v1")
    (attempt / "budget.jsonl").touch(exist_ok=False)
    result = {"schema_version": 1, "stage": "M0", "scope": "implementation evidence only", "benchmark_eligible": False,
              "cost_regime": "synthetic; not measured inference", "passed": all(c["passed"] for c in controls),
              "controls": controls, "control_count": len(controls), "model_calls": 0, "candidate_executions": 0,
              "artifact_hashes": implementation_hashes(), "attempt_path": attempt_path.as_posix(),
              "recorded_at": datetime.now(timezone.utc).isoformat(), "cpu_wall_seconds": time.perf_counter() - started,
              "budget_snapshot": resume_attempts(attempt / "budget.jsonl"), "workflow": workflow}
    write_json_atomic(attempt / "core.json", result)
    write_json_atomic(root / "core.json", result)
    return result


def render_report(run_dir: Path) -> str:
    root = Path(run_dir)
    if not (root / "core.json").exists():
        return "M0: unexecuted. No simulation evidence.\n\nM1–M6: unexecuted.\n"
    result = read_json(root / "core.json")
    status = "passed" if result["passed"] else "failed"
    lines = ["# M0 verification", "", "This is implementation evidence only. Scientific status: INCONCLUSIVE; natural benchmark unexecuted.", "",
             f"Core controls: {status} ({sum(c['passed'] for c in result['controls'])}/{result['control_count']}).",
             "Model calls/downloads: 0. Candidate executions: 0. Toy costs are synthetic, not local performance measurements.", "",
             "| Control | Result |", "| --- | --- |"]
    lines.extend(f"| {c['id']} | {'PASS' if c['passed'] else 'FAIL'} |" for c in result["controls"])
    lines.extend(["", f"Raw artifacts: `{(root / result['attempt_path']).as_posix()}`.", "",
                  "Simulation alone does not authorize a gate; ordinary tests and current artifact fingerprints are required."])
    prerequisite_gate = root.parent / "m1/gate.json"
    if prerequisite_gate.exists():
        from .records import GateResult, from_dict
        gate = from_dict(GateResult, read_json(prerequisite_gate))
        if gate.stage != "M1":
            raise ValueError("M1 report gate has the wrong stage")
        lines.extend(["", f"M1: {gate.status} (recorded execution gate).", *gate.reasons,
                      "", "M2–M5: unexecuted. This report summarizes the available evidence prefix."])
    else:
        lines.extend(["", "M1–M6: unexecuted."])
    return "\n".join(lines) + "\n"
