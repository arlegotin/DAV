from dataclasses import replace
import importlib
from pathlib import Path

import pytest

from depverify.records import GateResult


def pipeline():
    return importlib.import_module("depverify.pipeline")


def gate(status="GO", code="a" * 64):
    return GateResult("M0", status, "2026-09-29T00:00:00Z", {"code": code}, {"math": True}, (), (), {"model_seconds": 0.})


@pytest.mark.parametrize("status", ["NO_GO", "BLOCKED", "INCONCLUSIVE"])
def test_missing_or_non_go_gate_rejects_expensive_work(tmp_path, status):
    p, path = pipeline(), tmp_path / "m0.json"
    with pytest.raises(ValueError):
        p.require_gate(path, stage="M0", expected_hashes={"code": "a" * 64})
    p.write_gate(path, gate(status))
    with pytest.raises(ValueError):
        p.require_gate(path, stage="M0", expected_hashes={"code": "a" * 64})


def test_go_gate_requires_matching_stage_and_current_artifacts(tmp_path):
    p, path = pipeline(), tmp_path / "m0.json"
    p.write_gate(path, gate())
    assert p.require_gate(path, stage="M0", expected_hashes={"code": "a" * 64}).status == "GO"
    for stage, hashes in [("M1", {"code": "a" * 64}), ("M0", {"code": "b" * 64}), ("M0", {})]:
        with pytest.raises(ValueError):
            p.require_gate(path, stage=stage, expected_hashes=hashes)


def test_superseded_gate_is_preserved_in_immutable_history(tmp_path):
    p, path = pipeline(), tmp_path / "m0.json"
    p.write_gate(path, gate("BLOCKED"))
    p.write_gate(path, gate())
    p.write_gate(path, gate())
    assert len(list((tmp_path / "m0.history").glob("*.json"))) == 2
    assert p.require_gate(path, stage="M0", expected_hashes={"code": "a" * 64}).status == "GO"


def test_failed_criterion_cannot_be_written_as_go(tmp_path):
    with pytest.raises(ValueError):
        pipeline().write_gate(tmp_path / "m0.json", replace(gate(), criteria={"math": False}))


def test_revision_allowances_are_not_repeatable(tmp_path):
    p, path = pipeline(), tmp_path / "ledger.jsonl"
    for kind in ("pilot", "mechanism"):
        p.record_revision(path, kind=kind, reason="documented defect")
        p.record_revision(path, kind=kind, reason="documented defect")
        with pytest.raises(ValueError):
            p.record_revision(path, kind=kind, reason="try again for a favorable result")


def test_config_rejects_gate_bypass_and_reads_declared_caps(tmp_path):
    p = pipeline()
    config = Path(__file__).resolve().parents[1] / "config.toml"
    parsed = p.load_config(config)
    assert parsed["limits"]["model_call_seconds"] == 180
    bad = tmp_path / "bad.toml"
    bad.write_text("ignore_all_gates = true\n" + config.read_text())
    with pytest.raises(ValueError):
        p.load_config(bad)
