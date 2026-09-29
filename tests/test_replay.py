import importlib

import pytest

from depverify.records import CheckResult, Proposal, to_dict


def evaluation():
    return importlib.import_module("depverify.evaluate")


def make_evidence(check_metadata, *, public_verdict="PASS"):
    return {check: CheckResult("1" * 64, check, public_verdict if check == "T" else "PASS", "ok", "inspection only",
                               seconds, check_metadata | {"cache_hit": True, "lookup_seconds": .00001})
            for check, seconds in [("R1", 12.), ("R2", 3.), ("T", .2), ("D", 10.)]}


def two_review_policy(lineage, available, history):
    if history[0] is None:
        return "R1", "ok"
    if history[1] is None:
        return "R2", "ok"
    return "ACCEPT", "ok"


def test_only_requested_outcomes_are_revealed_and_original_costs_charged(actor_metadata, check_metadata):
    e = evaluation()
    proposal = Proposal("fake-001", "1" * 64, "pass", "ok", actor_metadata, 0.)
    observed = []
    def spy(lineage, available, history):
        observed.append((lineage, available, history))
        return two_review_policy(lineage, available, history)
    decision = e.replay_episode(proposal, "same_lineage", frozenset({"R1", "R2", "T", "D"}), spy,
                                make_evidence(check_metadata), policy_hash="2" * 64)
    assert decision.history == (("R1", "PASS"), ("R2", "PASS"))
    assert decision.action == "ACCEPT"
    assert decision.selected_check_seconds == 15.
    assert [h for _, _, h in observed] == [(None, None, None, None), ("PASS", None, None, None), ("PASS", "PASS", None, None)]
    assert all(isinstance(g, str) and isinstance(a, frozenset) and isinstance(h, tuple) for g, a, h in observed)


def test_duplicate_request_defers_after_one_charge(actor_metadata, check_metadata):
    proposal = Proposal("fake-001", "1" * 64, "pass", "ok", actor_metadata, 0.)
    decision = evaluation().replay_episode(proposal, "same_lineage", frozenset({"R1"}),
                                           lambda *args: ("R1", "ok"), make_evidence(check_metadata), policy_hash="2" * 64)
    assert (decision.action, decision.status) == ("DEFER", "duplicate_request")
    assert decision.history == (("R1", "PASS"),)
    assert decision.selected_check_seconds == 12.


def test_unavailable_request_has_no_charge_and_unknown_is_an_acquired_value(actor_metadata, check_metadata):
    proposal = Proposal("fake-001", "1" * 64, "pass", "ok", actor_metadata, 0.)
    unavailable = evaluation().replay_episode(proposal, "same_lineage", frozenset(),
                                             lambda *args: ("D", "ok"), {}, policy_hash="2" * 64)
    assert unavailable.status == "unavailable_request"
    assert unavailable.selected_check_seconds == 0.
    assert unavailable.history == ()
    evidence = {"D": CheckResult("1" * 64, "D", "UNKNOWN", "unavailable", "", 10., check_metadata)}
    def unknown_policy(lineage, available, history):
        return ("D", "ok") if history[3] is None else ("DEFER", "ok")
    unknown = evaluation().replay_episode(proposal, "same_lineage", frozenset({"D"}), unknown_policy,
                                         evidence, policy_hash="2" * 64)
    assert unknown.history == (("D", "UNKNOWN"),)
    assert unknown.selected_check_seconds == 10.


def test_unrequested_public_failure_is_invisible_but_acquired_failure_vetoes(actor_metadata, check_metadata):
    proposal = Proposal("fake-001", "1" * 64, "pass", "ok", actor_metadata, 0.)
    evidence = make_evidence(check_metadata, public_verdict="FAIL")
    always = lambda *args: ("ACCEPT", "ok")
    unseen = evaluation().replay_episode(proposal, "same_lineage", frozenset({"T"}), always, evidence, policy_hash="2" * 64)
    assert unseen.action == "ACCEPT" and unseen.history == ()
    def ask_t(lineage, available, history):
        return ("T", "ok") if history[2] is None else ("ACCEPT", "ok")
    seen = evaluation().replay_episode(proposal, "same_lineage", frozenset({"T"}), ask_t, evidence, policy_hash="2" * 64)
    assert (seen.action, seen.status) == ("DEFER", "public_fail_veto")
    assert seen.history == (("T", "FAIL"),)
    assert seen.selected_check_seconds == .2


def test_invalid_proposal_or_mismatched_evidence_cannot_accept(actor_metadata, check_metadata):
    proposal = Proposal("fake-001", "1" * 64, "broken", "syntax_error", actor_metadata, 0.)
    result = evaluation().replay_episode(proposal, "same_lineage", frozenset(), lambda *args: ("ACCEPT", "ok"), {}, policy_hash="2" * 64)
    assert (result.action, result.status) == ("DEFER", "invalid_proposal")
    proposal = Proposal("fake-001", "1" * 64, "pass", "ok", actor_metadata, 0.)
    bad = {"R1": CheckResult("3" * 64, "R1", "PASS", "ok", "", 12., check_metadata)}
    result = evaluation().replay_episode(proposal, "same_lineage", frozenset({"R1"}), lambda *args: ("R1", "ok"), bad, policy_hash="2" * 64)
    assert (result.action, result.status) == ("DEFER", "stale_evidence")
    assert result.selected_check_seconds == 0.


@pytest.mark.parametrize("output", [("NOT_A_CHECK", "ok"), "ACCEPT", ("ACCEPT", 2), ("ACCEPT", "calibration_invalid")])
def test_invalid_policy_output_cannot_accept(actor_metadata, output):
    proposal = Proposal("fake-001", "1" * 64, "pass", "ok", actor_metadata, 0.)
    result = evaluation().replay_episode(proposal, "same_lineage", frozenset(), lambda *args: output, {}, policy_hash="2" * 64)
    assert result.action == "DEFER"


def test_all_four_unknown_actions_still_terminate(actor_metadata, check_metadata):
    proposal = Proposal("fake-001", "1" * 64, "pass", "ok", actor_metadata, 0.)
    evidence = {c: CheckResult("1" * 64, c, "UNKNOWN", "ok", "", 0., check_metadata) for c in ("R1", "R2", "T", "D")}
    def acquire_all(lineage, available, history):
        return next(((c, "ok") for i, c in enumerate(("R1", "R2", "T", "D")) if history[i] is None), ("DEFER", "ok"))
    result = evaluation().replay_episode(proposal, "same_lineage", frozenset(evidence), acquire_all, evidence, policy_hash="2" * 64)
    assert len(result.history) == 4
    assert result.action == "DEFER"
    assert result.selected_check_seconds == 0.
