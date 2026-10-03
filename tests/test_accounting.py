from dataclasses import replace
import importlib

import pytest

from depverify.records import Decision, Proposal


def evaluation():
    return importlib.import_module("depverify.evaluate")


@pytest.mark.parametrize("action,label,loss", [("ACCEPT", 1, 8.), ("ACCEPT", 0, 28.), ("DEFER", 1, 13.), ("DEFER", 0, 13.)])
def test_loss_charges_common_selected_and_outcome_costs(actor_metadata, action, label, loss):
    proposal = Proposal("fake-001", "1" * 64, "pass", "ok", actor_metadata, 2.)
    decision = Decision("1" * 64, "2" * 64, (("R1", "PASS"),), action, "ok", 4., 1., 1.)
    row = evaluation().score_decision(proposal, decision, label, unit_seconds=2.)
    assert row["loss"] == loss
    assert row["total_seconds"] == 16.
    assert row["normalized_work"] == 8.
    assert row["correct_accept"] == int(action == "ACCEPT" and label == 1)
    assert row["incorrect_accept"] == int(action == "ACCEPT" and label == 0)
    assert row["deferral"] == int(action == "DEFER")


@pytest.mark.parametrize("unit", [0., -1., float("nan"), float("inf"), True])
def test_invalid_unit_cannot_create_favorable_loss(actor_metadata, unit):
    proposal = Proposal("fake-001", "1" * 64, "pass", "ok", actor_metadata, 0.)
    decision = Decision("1" * 64, "2" * 64, (), "DEFER", "ok", 0., 0., 0.)
    with pytest.raises(ValueError):
        evaluation().score_decision(proposal, decision, 0, unit_seconds=unit)


def score_row(actor_metadata, episode, root, action, label, actor_seconds):
    proposal = Proposal(episode, "1" * 64, "pass", "ok", actor_metadata | {"elapsed_seconds": actor_seconds}, 0.)
    decision = Decision("1" * 64, "2" * 64, (), action, "ok", 0., 0., 0.)
    return evaluation().score_decision(proposal, decision, label, unit_seconds=2.) | {"root_group_id": root}


def test_all_deferred_has_nonzero_loss_and_undefined_efficiency(actor_metadata):
    rows = [score_row(actor_metadata, "one", "r1", "DEFER", 0, 8.), score_row(actor_metadata, "two", "r2", "DEFER", 1, 8.)]
    result = evaluation().summarize(rows)
    assert result["mean_loss"] == 9.
    assert result["correct_accepts"] == result["incorrect_accepts"] == 0
    assert result["deferrals"] == 2
    assert result["seconds_per_correct_accept"] is None
    assert result["efficiency_status"] == "undefined_no_correct_accepts"


def test_variants_do_not_inflate_root_weight_or_root_count(actor_metadata):
    one = score_row(actor_metadata, "one", "r1", "ACCEPT", 1, 2.)
    two = score_row(actor_metadata, "two", "r2", "ACCEPT", 1, 10.)
    original = evaluation().summarize([one, two])
    copies = [one | {"episode_id": f"variant-{i}"} for i in range(10)]
    replicated = evaluation().summarize([*copies, two])
    assert replicated["root_groups"] == original["root_groups"] == 2
    assert replicated["mean_loss"] == original["mean_loss"] == 3.
    assert replicated["seconds_per_correct_accept"] == original["seconds_per_correct_accept"] == 6.


def test_unresolved_labels_remain_in_ledger_without_optimistic_scoring(actor_metadata):
    known = score_row(actor_metadata, "one", "r1", "ACCEPT", 1, 2.)
    unresolved = score_row(actor_metadata, "two", "r2", "ACCEPT", "LABEL_UNRESOLVED", 10.)
    assert unresolved["loss"] is None
    result = evaluation().summarize([known, unresolved])
    assert result["episodes"] == 2
    assert result["analyzed_episodes"] == 1
    assert result["unresolved_labels"] == 1
    assert result["total_seconds"] == 12.


def test_duplicate_episodes_and_public_label_contradictions_block_analysis(actor_metadata):
    row = score_row(actor_metadata, "one", "r1", "ACCEPT", 1, 2.)
    with pytest.raises(ValueError):
        evaluation().summarize([row, row])
    proposal = Proposal("one", "1" * 64, "pass", "ok", actor_metadata, 0.)
    public_fail = Decision("1" * 64, "2" * 64, (("T", "FAIL"),), "DEFER", "ok", 0., 0., 0.)
    with pytest.raises(ValueError):
        evaluation().score_decision(proposal, public_fail, 1, unit_seconds=2.)
    with pytest.raises(ValueError):
        evaluation().score_decision(replace(proposal, status="syntax_error"), replace(public_fail, history=()), 1, unit_seconds=2.)


def test_acceptance_rates_weight_roots_equally_with_unequal_variants(actor_metadata):
    rows=[score_row(actor_metadata,'a','one','ACCEPT',1,2.)]
    rows += [score_row(actor_metadata,f'b{i}','two','ACCEPT',0,2.) for i in range(3)]
    result=evaluation().summarize(rows)
    assert result['correct_accepts_per_attempt']==.5
    assert result['incorrect_accepts_per_attempt']==.5
    assert result['incorrect_among_accepted']==.5
    assert result['raw_correct_accepts_per_attempt']==.25
