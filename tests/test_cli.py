import importlib
import json
from pathlib import Path
import subprocess
import sys


def run_cli(cwd, *args):
    return subprocess.run([sys.executable, "-m", "depverify", *args], cwd=cwd, capture_output=True, text=True, timeout=30)


def test_fake_doctor_runs_without_model_or_engine(tmp_path):
    result = run_cli(tmp_path, "doctor", "--fake")
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["mode"] == "fake"
    assert output["model_calls"] == output["candidate_executions"] == 0
    assert output["mlx_loaded"] is False
    assert output["container_engine_used"] is False


def test_cli_simulation_and_prefix_report_are_explicitly_fake(tmp_path):
    first = run_cli(tmp_path, "simulate", "--suite", "core")
    assert first.returncode == 0, first.stderr
    summary = json.loads(first.stdout)
    assert summary["passed"] is True and summary["benchmark_eligible"] is False
    report = run_cli(tmp_path, "report")
    assert report.returncode == 0
    assert "M0" in report.stdout
    assert "implementation evidence only" in report.stdout
    assert "M1–M6: unexecuted" in report.stdout
    assert not (tmp_path / "runs/m0/gate.json").exists()


def test_report_works_before_any_simulation(tmp_path):
    result = run_cli(tmp_path, "report")
    assert result.returncode == 0
    assert "unexecuted" in result.stdout


def test_future_command_and_gate_bypass_are_rejected_without_artifacts(tmp_path):
    for args in [("collect", "--split", "test"), ("simulate", "--suite", "core", "--ignore-all-gates")]:
        result = run_cli(tmp_path, *args)
        assert result.returncode == 2
        assert list(tmp_path.iterdir()) == []


def test_fake_cli_does_not_import_mlx_or_contact_container_engine(tmp_path, monkeypatch):
    cli = importlib.import_module("depverify.__main__")
    original = __import__
    def guarded_import(name, *args, **kwargs):
        assert not name.startswith(("mlx", "docker"))
        return original(name, *args, **kwargs)
    monkeypatch.setattr("builtins.__import__", guarded_import)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["doctor", "--fake"]) == 0
