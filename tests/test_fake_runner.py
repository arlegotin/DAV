import importlib
import subprocess

import pytest


def runner():
    return importlib.import_module("depverify.runner")


def test_fake_runner_returns_registered_json_without_running_code(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("fake runner attempted host execution")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr("builtins.eval", forbidden)
    monkeypatch.setattr("time.sleep", forbidden)
    registry = {"1" * 64: {"status": "ok", "inputs": [2, {"label": "public"}], "outputs": [2, {"label": "public"}], "elapsed_seconds": .3}}
    fake = runner().FakeRunner(registry)
    registry["1" * 64]["outputs"][0] = "mutated"
    result = fake.run("1" * 64, [2, {"label": "public"}])
    assert result["outputs"] == [2, {"label": "public"}]
    assert result["elapsed_seconds"] == .3
    assert result["fake"] is True
    assert result["invocation"] == 1
    assert runner().FakeRunner({"1" * 64: {"status": "ok", "inputs": [], "outputs": [], "elapsed_seconds": 0.}}).run("1" * 64, [])["invocation"] == 1


def test_unregistered_or_mismatched_input_count_does_not_fabricate_success():
    fake = runner().FakeRunner({"1" * 64: {"status": "ok", "inputs": [2], "outputs": [2], "elapsed_seconds": .3}})
    with pytest.raises(ValueError):
        fake.run("2" * 64, [2])
    with pytest.raises(ValueError):
        fake.run("1" * 64, [2, 3])


def test_fake_response_is_bound_to_exact_inputs():
    fake = runner().FakeRunner({"1" * 64: {"status": "ok", "inputs": [2], "outputs": [2], "elapsed_seconds": .3}})
    with pytest.raises(ValueError):
        fake.run("1" * 64, [3])
