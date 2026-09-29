import importlib

import pytest

from depverify.records import CheckResult, Proposal, canonical_json, to_dict
from test_replay import make_evidence


def one_review_policy(lineage, available, history):
    return ("R1", "ok") if history[0] is None else ("ACCEPT", "ok")


@pytest.mark.parametrize("check", ["R2", "T", "D"])
@pytest.mark.parametrize("verdict", ["PASS", "FAIL", "UNKNOWN"])
def test_perturbed_unrequested_value_cannot_change_next_action(actor_metadata, check_metadata, check, verdict, monkeypatch):
    e = importlib.import_module("depverify.evaluate")
    monkeypatch.setattr(e.time, "perf_counter", lambda: 0.)
    proposal = Proposal("fake-001", "1" * 64, "pass", "ok", actor_metadata, 0.)
    evidence = make_evidence(check_metadata)
    original = e.replay_episode(proposal, "same_lineage", frozenset(evidence), one_review_policy, evidence, policy_hash="2" * 64)
    evidence[check] = CheckResult("1" * 64, check, verdict, "ok", "different private inspection text", 100., check_metadata)
    changed = e.replay_episode(proposal, "same_lineage", frozenset(evidence), one_review_policy, evidence, policy_hash="2" * 64)
    assert canonical_json(to_dict(original)) == canonical_json(to_dict(changed))


def test_changing_private_label_file_cannot_change_any_trajectory(tmp_path, actor_metadata, check_metadata, monkeypatch):
    e = importlib.import_module("depverify.evaluate")
    monkeypatch.setattr(e.time, "perf_counter", lambda: 0.)
    monkeypatch.chdir(tmp_path)
    private = tmp_path / "labels.jsonl"
    proposals = [Proposal(f"fake-{i}", "1" * 64, "pass", "ok", actor_metadata, 0.) for i in range(3)]
    def trajectories():
        return [canonical_json(to_dict(e.replay_episode(p, "same_lineage", frozenset({"R1"}), one_review_policy,
                                                       make_evidence(check_metadata), policy_hash="2" * 64))) for p in proposals]
    private.write_text('\n'.join(f'{{"episode_id":"fake-{i}","Y":0}}' for i in range(3)))
    before = trajectories()
    private.write_text('\n'.join(f'{{"episode_id":"fake-{i}","Y":1}}' for i in range(3)))
    assert trajectories() == before


def test_replay_does_not_enumerate_full_records(actor_metadata, check_metadata):
    e = importlib.import_module("depverify.evaluate")
    class RequestedOnly(dict):
        def __iter__(self):
            raise AssertionError("full evidence enumeration")
        def __getitem__(self, key):
            if key != "R1":
                raise AssertionError("unrequested evidence read")
            return super().__getitem__(key)
    proposal = Proposal("fake-001", "1" * 64, "pass", "ok", actor_metadata, 0.)
    result = e.replay_episode(proposal, "same_lineage", frozenset({"R1", "T"}), one_review_policy,
                              RequestedOnly(make_evidence(check_metadata)), policy_hash="2" * 64)
    assert result.history == (("R1", "PASS"),)
    assert result.action == "ACCEPT"
