from concurrent.futures import ThreadPoolExecutor
import importlib

import pytest


def pipeline():
    return importlib.import_module("depverify.pipeline")


def limits(total=600., stage=600.):
    return {"total_seconds": {"model": total}, "stage_seconds": {"M1": {"model": stage}, "M2": {"model": stage}},
            "per_call_seconds": {"model": 180., "execution": 10.}}


@pytest.mark.parametrize("caps", [limits(total=179.), limits(stage=179.)])
def test_timeout_reservation_is_denied_before_call_can_launch(tmp_path, caps):
    p, called = pipeline(), []
    with pytest.raises(p.BudgetStop):
        p.reserve(tmp_path / "ledger.jsonl", attempt_id="one", stage="M1", work_kind="model",
                  allowance_seconds=180., limits=caps)
        called.append("call")
    assert called == []
    assert p.resume_attempts(tmp_path / "ledger.jsonl")["reserved_model_seconds"] == 0.


def test_settlement_releases_allowance_and_is_idempotent(tmp_path):
    p, path = pipeline(), tmp_path / "ledger.jsonl"
    reservation = p.reserve(path, attempt_id="one", stage="M1", work_kind="model", allowance_seconds=180., limits=limits())
    assert p.resume_attempts(path)["reserved_model_seconds"] == 180.
    p.settle(path, reservation_id=reservation, actual_seconds=12., status="ok")
    before = path.read_bytes()
    p.settle(path, reservation_id=reservation, actual_seconds=12., status="ok")
    assert path.read_bytes() == before
    state = p.resume_attempts(path)
    assert state["model_seconds"] == 12.
    assert state["reserved_model_seconds"] == 0.
    assert state["attempts"]["one"]["released_seconds"] == 168.
    with pytest.raises(ValueError):
        p.settle(path, reservation_id=reservation, actual_seconds=13., status="ok")


def test_execution_dimension_does_not_spend_model_budget(tmp_path):
    p, path = pipeline(), tmp_path / "ledger.jsonl"
    reservation = p.reserve(path, attempt_id="public-test", stage="M1", work_kind="execution", allowance_seconds=10., limits=limits(0., 0.))
    p.settle(path, reservation_id=reservation, actual_seconds=.4, status="ok")
    state = p.resume_attempts(path)
    assert state["model_seconds"] == state["reserved_model_seconds"] == 0.
    assert state["execution_seconds"] == .4


def test_full_timeout_cannot_be_replaced_by_optimistic_expected_duration(tmp_path):
    with pytest.raises(ValueError):
        pipeline().reserve(tmp_path / "ledger.jsonl", attempt_id="one", stage="M1", work_kind="model",
                           allowance_seconds=12., limits=limits())


def test_two_concurrent_reservations_cannot_overspend(tmp_path):
    p, path = pipeline(), tmp_path / "ledger.jsonl"
    def reserve_one(index):
        try:
            p.reserve(path, attempt_id=str(index), stage="M1", work_kind="model", allowance_seconds=180., limits=limits(180., 180.))
            return "reserved"
        except p.BudgetStop:
            return "denied"
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(reserve_one, (1, 2)))
    assert sorted(outcomes) == ["denied", "reserved"]
    assert p.resume_attempts(path)["reserved_model_seconds"] == 180.


def test_limit_changes_do_not_reset_existing_work(tmp_path):
    p, path = pipeline(), tmp_path / "ledger.jsonl"
    p.reserve(path, attempt_id="one", stage="M1", work_kind="model", allowance_seconds=180., limits=limits())
    with pytest.raises(ValueError):
        p.reserve(path, attempt_id="two", stage="M1", work_kind="model", allowance_seconds=180., limits=limits(1200., 1200.))
    assert p.resume_attempts(path)["reserved_model_seconds"] == 180.


def test_repeated_reservation_cannot_authorize_duplicate_call(tmp_path):
    p, path = pipeline(), tmp_path / "ledger.jsonl"
    reservation = p.reserve(path, attempt_id="one", stage="M1", work_kind="model", allowance_seconds=180., limits=limits())
    with pytest.raises(ValueError):
        p.reserve(path, attempt_id="one", stage="M1", work_kind="model", allowance_seconds=180., limits=limits())
    p.settle(path, reservation_id=reservation, actual_seconds=12., status="ok")
    with pytest.raises(ValueError):
        p.reserve(path, attempt_id="one", stage="M1", work_kind="model", allowance_seconds=180., limits=limits())
    assert p.resume_attempts(path)["model_seconds"] == 12.


def test_actual_overrun_is_retained_and_stops_expansion(tmp_path):
    p, path = pipeline(), tmp_path / "ledger.jsonl"
    reservation = p.reserve(path, attempt_id="one", stage="M1", work_kind="model", allowance_seconds=180., limits=limits())
    p.settle(path, reservation_id=reservation, actual_seconds=181., status="model_timeout")
    assert p.resume_attempts(path)["model_seconds"] == 181.
    with pytest.raises(p.BudgetStop):
        p.reserve(path, attempt_id="two", stage="M1", work_kind="model", allowance_seconds=180., limits=limits())
