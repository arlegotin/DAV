import importlib

import pytest

from test_budget import limits


def pipeline():
    return importlib.import_module("depverify.pipeline")


def test_crash_after_reservation_is_not_free_and_resume_is_idempotent(tmp_path):
    p, path = pipeline(), tmp_path / "ledger.jsonl"
    p.reserve(path, attempt_id="one", stage="M1", work_kind="model", allowance_seconds=180., limits=limits())
    before = path.read_bytes()
    first, second = p.resume_attempts(path), p.resume_attempts(path)
    assert first == second
    assert path.read_bytes() == before
    assert first["model_seconds"] == 0.
    assert first["reserved_model_seconds"] == first["accounted_model_seconds"] == 180.
    assert first["attempts"]["one"]["status"] == "pending"
    assert first["attempts"]["one"]["retry_allowed"] is False


def test_partial_tail_is_preserved_and_pending_work_stays_reserved(tmp_path):
    p, path = pipeline(), tmp_path / "ledger.jsonl"
    p.reserve(path, attempt_id="one", stage="M1", work_kind="model", allowance_seconds=180., limits=limits())
    tail = b'{"event_id":"settle:reserve:one","actual_seconds":'
    with path.open("ab") as stream:
        stream.write(tail)
    state = p.resume_attempts(path)
    artifacts = list(tmp_path.glob("ledger.partial-*.bin"))
    assert len(artifacts) == 1 and artifacts[0].read_bytes() == tail
    assert state["accounted_model_seconds"] == 180.
    assert p.resume_attempts(path) == state


@pytest.mark.parametrize("status,allowed", [("infrastructure_error", True), ("model_timeout", True),
                                          ("format_error", False), ("candidate_failure", False), ("ok", False)])
def test_at_most_one_infrastructure_retry_and_both_costs_retained(tmp_path, status, allowed):
    p, path = pipeline(), tmp_path / "ledger.jsonl"
    reservation = p.reserve(path, attempt_id="one", stage="M1", work_kind="model", allowance_seconds=180., limits=limits())
    p.settle(path, reservation_id=reservation, actual_seconds=12., status=status)
    assert p.resume_attempts(path)["attempts"]["one"]["retry_allowed"] is allowed
    if allowed:
        retry = p.reserve(path, attempt_id="one::retry1", stage="M1", work_kind="model", allowance_seconds=180., limits=limits())
        p.settle(path, reservation_id=retry, actual_seconds=10., status="ok")
        assert p.resume_attempts(path)["model_seconds"] == 22.
        with pytest.raises(ValueError):
            p.reserve(path, attempt_id="one::retry2", stage="M1", work_kind="model", allowance_seconds=180., limits=limits())
        assert p.resume_attempts(path)["attempts"]["one"]["retry_allowed"] is False
    else:
        with pytest.raises(ValueError):
            p.reserve(path, attempt_id="one::retry1", stage="M1", work_kind="model", allowance_seconds=180., limits=limits())


def test_conflicting_reservation_and_corrupt_complete_event_block_resume(tmp_path):
    p, path = pipeline(), tmp_path / "ledger.jsonl"
    p.reserve(path, attempt_id="one", stage="M1", work_kind="model", allowance_seconds=180., limits=limits())
    with pytest.raises(ValueError):
        p.reserve(path, attempt_id="one", stage="M2", work_kind="model", allowance_seconds=180., limits=limits())
    with path.open("ab") as stream:
        stream.write(b'{"broken"}\n')
    before = path.read_bytes()
    with pytest.raises(ValueError):
        p.resume_attempts(path)
    assert path.read_bytes() == before
