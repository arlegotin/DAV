import importlib
from pathlib import Path

import pytest

GIB = 2**30


def resources():
    return importlib.import_module("depverify.resources")


def item(name, device, free, extra, **changes):
    return {"name": name, "path": "/example/" + name, "device": device,
            "free_bytes": free * GIB, "additional_bytes": extra * GIB} | changes


def test_workspace_is_not_charged_for_downloads_on_another_filesystem():
    plan = resources().storage_plan([item("workspace", 1, 13, 1), item("model", 2, 146, 5),
                                     item("dependencies", 1, 13, 1), item("image", 2, 146, 1)])
    assert plan["passed"] is True
    assert plan["volumes"]["1"]["required_bytes"] == 4 * GIB
    assert plan["volumes"]["2"]["required_bytes"] == 10 * GIB


def test_shared_filesystem_costs_are_aggregated_before_margin():
    plan = resources().storage_plan([item("model", 1, 8, 4), item("image", 1, 8, 2)])
    assert plan["passed"] is False
    assert plan["volumes"]["1"]["required_bytes"] == 10 * GIB


def test_only_complete_verified_cache_can_remove_download_requirement():
    cached = item("model", 1, 2, 8, cached=True, cache_verified=True)
    assert resources().storage_plan([cached])["passed"] is True
    assert resources().storage_plan([cached])["volumes"]["1"]["additional_bytes"] == 0
    with pytest.raises(ValueError):
        resources().storage_plan([cached | {"cache_verified": False}])


def test_unknown_asset_size_does_not_authorize_download():
    plan = resources().storage_plan([item("model", 1, 146, 0, additional_bytes=None)])
    assert plan["passed"] is False
    assert "unknown_asset_size" in plan["reasons"]


@pytest.mark.parametrize("field,value", [("free_bytes", -1), ("additional_bytes", float("nan")),
                                         ("additional_bytes", True), ("device", None)])
def test_invalid_storage_measurement_is_rejected(field, value):
    with pytest.raises(ValueError):
        resources().storage_plan([item("model", 1, 146, 5) | {field: value}])


def test_amended_config_has_storage_budget_and_keeps_execution_caps():
    from depverify.pipeline import load_config
    config = load_config(Path(__file__).resolve().parents[1] / "config.toml")
    assert config["storage"]["planning_margin"] == 1.5
    assert config["storage"]["reserve_bytes"] == GIB
    assert config["limits"]["model_call_seconds"] == 180
    assert config["budgets"]["stage_model_seconds"]["M1"] == 900
