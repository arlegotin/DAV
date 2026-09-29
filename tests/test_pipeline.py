import importlib

import pytest

from depverify.records import CheckResult, Task, proposal_key
from depverify.policy import always_accept, always_defer, test_only as t_policy


def pipeline():
    return importlib.import_module("depverify.pipeline")


def evidence_for(task, replacement, check_metadata):
    p = pipeline()
    key = proposal_key(task, replacement, p.FAKE_ENVIRONMENT, p.FAKE_CHECK_VERSIONS)
    return {c: CheckResult(key, c, "PASS", "ok", "fake", .2, check_metadata) for c in ("R1", "R2", "T", "D")}


@pytest.mark.parametrize("policy,action", [(always_accept, "ACCEPT"), (always_defer, "DEFER"), (t_policy, "ACCEPT")])
def test_fake_pipeline_applies_only_intended_file_or_defers(tmp_path, task_fields, check_metadata, policy, action):
    p = pipeline()
    task = Task(**task_fields)
    replacement = "def solve(x):\n    return x\n"
    proposal, decision = p.run_fake_episode(task, replacement, evidence_for(task, replacement, check_metadata), policy, tmp_path)
    assert proposal.status == "ok"
    assert decision.action == action
    copies = list(tmp_path.glob(".depverify-*"))
    assert len(copies) == 1
    assert (copies[0] / "candidate.py").read_text() == (replacement if action == "ACCEPT" else task.base_files["candidate.py"])
    assert (copies[0] / "support.py").read_text() == task.base_files["support.py"]


def test_malformed_proposal_is_retained_and_never_checked(tmp_path, task_fields, check_metadata):
    p = pipeline()
    task = Task(**task_fields)
    proposal, decision = p.run_fake_episode(task, "def solve(:", {}, always_accept, tmp_path)
    assert proposal.status == "syntax_error"
    assert (decision.action, decision.status) == ("DEFER", "invalid_proposal")
    assert decision.history == ()


def test_core_suite_writes_reconciled_fake_evidence_without_research_gate(tmp_path):
    evaluation = importlib.import_module("depverify.evaluate")
    result = evaluation.run_core_suite(tmp_path)
    assert result["passed"] is True
    assert result["benchmark_eligible"] is False
    assert result["model_calls"] == result["candidate_executions"] == 0
    names = {c["id"] for c in result["controls"]}
    assert {"independent_checks", "copied_checks", "mixed_modalities", "all_useless", "free_perfect", "expensive_perfect",
            "asymmetric_failure", "xor_complementarity", "zero_unknown_support", "missing_actions", "duplicate_request",
            "altered_unrequested", "hidden_labels", "cost_accounting", "temporary_permissions", "coupling_gain",
            "coupling_no_gain", "public_fail_veto", "all_unknown", "zero_cost"}.issubset(names)
    assert (tmp_path / "core.json").exists()
    assert not (tmp_path / "gate.json").exists()
    attempt = tmp_path / result["attempt_path"]
    assert (attempt / "proposals.jsonl").exists()
    assert (attempt / "decisions.jsonl").exists()
    assert (attempt / "private/labels.jsonl").exists()
