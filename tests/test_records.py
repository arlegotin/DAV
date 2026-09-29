import importlib
import json

import pytest


def records():
    return importlib.import_module("depverify.records")


def test_canonical_hash_ignores_mapping_order_but_not_content():
    r = records()
    assert r.canonical_json({"b": 2, "a": 1}) == b'{"a":1,"b":2}'
    assert r.sha256_bytes(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_json_is_rejected(value):
    with pytest.raises(ValueError):
        records().canonical_json({"value": value})


def test_five_records_round_trip(task_fields, actor_metadata, check_metadata):
    r = records()
    task = r.Task(**task_fields)
    key = r.proposal_key(task, "def solve(x):\n    return x\n", {"version": "fake"}, {"R1": "v1"})
    values = [
        task,
        r.Proposal(task.episode_id, key, "def solve(x):\n    return x\n", "ok", actor_metadata, 2.),
        r.CheckResult(key, "R1", "PASS", "ok", "Matches.", 12., check_metadata),
        r.Decision(key, "e" * 64, (("R1", "PASS"),), "ACCEPT", "ok", 12., 1., 1.),
        r.GateResult("M0", "GO", "2026-09-29T00:00:00Z", {"code": "f" * 64},
                     {"controls": True}, (), ("runs/m0/core.json",), {"model_seconds": 0.}),
    ]
    for value in values:
        serialized = json.loads(r.canonical_json(r.to_dict(value)))
        assert serialized["schema_version"] == 1
        restored = r.from_dict(type(value), serialized)
        assert r.to_dict(restored) == r.to_dict(value)


def test_all_proposal_identity_inputs_are_bound(task_fields):
    r = records()
    task = r.Task(**task_fields)
    replacement = "def solve(x):\n    return x\n"
    base = r.proposal_key(task, replacement, {"v": 1}, {"R1": "1"})
    assert base != r.proposal_key(task, replacement + "\n", {"v": 1}, {"R1": "1"})
    assert base != r.proposal_key(task, replacement, {"v": 2}, {"R1": "1"})
    assert base != r.proposal_key(task, replacement, {"v": 1}, {"R1": "2"})
    for field, value in [("contract", "Return a copy of x."),
                         ("base_files", {"candidate.py": "def solve(x): return 0"}),
                         ("source_manifest", {"A": {"version": "2"}})]:
        changed = r.Task(**(task_fields | {field: value}))
        assert base != r.proposal_key(changed, replacement, {"v": 1}, {"R1": "1"})


def test_task_does_not_accept_hidden_fields(task_fields):
    r = records()
    for field in ("label", "hidden_tests", "reference_implementation", "condition"):
        with pytest.raises((TypeError, ValueError)):
            r.Task(**(task_fields | {field: 1}))
    with pytest.raises(ValueError):
        r.Task(**(task_fields | {"source_manifest": {"label": 1}}))


def test_public_json_values_can_contain_label_and_condition_keys(task_fields):
    public = ({"input": {"label": "public data"}, "expected": {"condition": True}},)
    task = records().Task(**(task_fields | {"public_tests": public}))
    assert task.public_tests[0]["expected"]["condition"] is True


def test_records_do_not_change_when_input_metadata_changes(task_fields, actor_metadata):
    r = records()
    task = r.Task(**task_fields)
    proposal = r.Proposal("fake-001", "1" * 64, "pass", "ok", actor_metadata, 0.)
    before = r.canonical_json(r.to_dict(task)), r.canonical_json(r.to_dict(proposal))
    task_fields["base_files"]["support.py"] = "CHANGED"
    actor_metadata["sampling_settings"]["temperature"] = 1.
    assert before == (r.canonical_json(r.to_dict(task)), r.canonical_json(r.to_dict(proposal)))
    with pytest.raises(TypeError):
        task.base_files["candidate.py"] = "CHANGED"


@pytest.mark.parametrize("field,value", [("input_tokens", -1), ("output_tokens", True),
                                         ("elapsed_seconds", -1.), ("elapsed_seconds", float("nan"))])
def test_actor_costs_and_tokens_are_validated(actor_metadata, field, value):
    with pytest.raises(ValueError):
        records().Proposal("fake-001", "1" * 64, "pass", "ok", actor_metadata | {field: value}, 0.)


def test_missing_required_actor_and_check_metadata_is_rejected(actor_metadata, check_metadata):
    r = records()
    actor_metadata.pop("tokenizer_revision")
    with pytest.raises(ValueError):
        r.Proposal("fake-001", "1" * 64, "pass", "ok", actor_metadata, 0.)
    check_metadata.pop("prompt_hash")
    with pytest.raises(ValueError):
        r.CheckResult("1" * 64, "R1", "PASS", "ok", "", 0., check_metadata)


def test_timeout_flags_cannot_be_loaded_as_success(actor_metadata, check_metadata):
    r = records()
    with pytest.raises(ValueError):
        r.Proposal("fake-001", "1" * 64, "pass", "ok", actor_metadata | {"timed_out": True}, 0.)
    for check in ("R1", "R2", "T", "D"):
        with pytest.raises(ValueError):
            r.CheckResult("1" * 64, check, "PASS", "ok", "", 180., check_metadata | {"timed_out": True})


@pytest.mark.parametrize("status", ["output_limit", "candidate_failure", "candidate_timeout", "unsupported_status"])
def test_failed_check_status_cannot_load_as_pass(check_metadata, status):
    r = records()
    value = r.to_dict(r.CheckResult("1" * 64, "T", "PASS", "ok", "", 10., check_metadata))
    value["status"] = status
    with pytest.raises(ValueError):
        r.from_dict(r.CheckResult, value)


@pytest.mark.parametrize("status", ["candidate_failure", "candidate_timeout"])
def test_candidate_failure_status_requires_an_executable_check(check_metadata, status):
    with pytest.raises(ValueError):
        records().CheckResult("1" * 64, "R1", "FAIL", status, "", 10., check_metadata)


def test_unsupported_schema_and_extra_record_fields_fail(task_fields):
    r = records()
    data = r.to_dict(r.Task(**task_fields))
    with pytest.raises(ValueError):
        r.from_dict(r.Task, data | {"schema_version": 2})
    with pytest.raises(ValueError):
        r.from_dict(r.Task, data | {"label": 1})


@pytest.mark.parametrize("history,action", [((("R1", "PASS"), ("R1", "PASS")), "ACCEPT"),
                                           ((("T", "FAIL"),), "ACCEPT")])
def test_decision_rejects_duplicate_history_or_accept_after_public_failure(history, action):
    with pytest.raises(ValueError):
        records().Decision("1" * 64, "2" * 64, history, action, "ok", 0., 0., 0.)


def test_strict_json_and_atomic_record_write(tmp_path):
    r = records()
    path = tmp_path / "nested" / "record.json"
    r.write_json_atomic(path, {"value": 1})
    assert r.read_json(path) == {"value": 1}
    assert len(list(path.parent.iterdir())) == 1
    for text in ('{"value":1,"value":2}', '{"value":NaN}', '{"value":Infinity}'):
        path.write_text(text)
        with pytest.raises(ValueError):
            r.read_json(path)


def test_jsonl_duplicate_is_idempotent_and_conflict_preserves_file(tmp_path):
    r = records()
    path = tmp_path / "events.jsonl"
    assert r.append_event(path, {"event_id": "one", "seconds": 12.}) is True
    assert r.append_event(path, {"seconds": 12., "event_id": "one"}) is False
    with pytest.raises(ValueError):
        r.append_event(path, {"event_id": "one", "seconds": 13.})
    assert len(path.read_text().splitlines()) == 1
    assert r.read_events(path) == [{"event_id": "one", "seconds": 12.}]
