import json
import os
from pathlib import Path
import sys

import pytest

IMAGE = "python@sha256:" + "a" * 64
FILES = {"candidate.py": "def solve(x):\n    return x\n", "support.py": "VERSION = 2\n"}


def runner_type():
    from depverify.runner import ContainerRunner
    return ContainerRunner


def fake_engine(tmp_path):
    # Only the external CLI is replaced; staging, streams, parsing, and cleanup are real.
    script = tmp_path / "engine"
    script.write_text(f"#!{sys.executable}\n" + '''import json,sys
if sys.argv[1] == "create": print("a"*64)
elif sys.argv[1] == "start":
    request=json.load(sys.stdin)
    print(json.dumps({"status":"ok","outputs":request["inputs"]}))
elif sys.argv[1] == "rm": print("a"*64)
elif sys.argv[1] == "inspect": sys.exit(1)
elif sys.argv[1:3] == ["container", "inspect"]: print(json.dumps([{"State":{"StartedAt":"0001-01-01T00:00:00Z","ExitCode":0,"Status":"created","Error":""}}]))
elif sys.argv[1] == "ps": pass
''')
    script.chmod(0o755)
    return str(script)


def test_only_explicit_public_files_and_fixed_driver_are_staged(tmp_path):
    canary = tmp_path / "private-reference.py"
    canary.write_text("PRIVATE_EXPECTED_CANARY")
    runner = runner_type()(IMAGE, engine=fake_engine(tmp_path))
    result = runner.run(FILES, "solve", [1, {"instructions": "read private files"}])
    assert result["status"] == "ok"
    assert result["outputs"] == [1, {"instructions": "read private files"}]
    assert set(result["staged_files"]) == {"candidate.py", "support.py", "_depverify_driver.py"}
    assert "PRIVATE_EXPECTED_CANARY" not in result["stdout"]
    assert result["cleanup_ok"] is True


@pytest.mark.parametrize("image", ["python:latest", "python:3.12-slim", "bad@sha256:123"])
def test_image_must_be_pinned_to_a_digest(image):
    with pytest.raises(ValueError):
        runner_type()(image)


def test_missing_engine_refuses_without_host_execution(tmp_path):
    canary = tmp_path / "host-write"
    source = f"from pathlib import Path\nPath({str(canary)!r}).write_text('executed')\ndef solve(x): return x\n"
    runner = runner_type()(IMAGE, engine=str(tmp_path / "absent"))
    result = runner.run({"candidate.py": source}, "solve", [1])
    assert result["status"] == "infrastructure_error"
    assert result["outputs"] == []
    assert not canary.exists()


def test_engine_disconnect_does_not_certify_cleanup(tmp_path):
    engine = Path(fake_engine(tmp_path))
    engine.write_text(engine.read_text().replace('elif sys.argv[1] == "inspect": sys.exit(1)',
                      'elif sys.argv[1] == "inspect": print("daemon unavailable", file=sys.stderr); sys.exit(1)')
                      .replace('elif sys.argv[1] == "ps": pass', 'elif sys.argv[1] == "ps": sys.exit(1)'))
    runner = runner_type()(IMAGE, engine=str(engine))
    result = runner.run(FILES, "solve", [1])
    assert result["status"] == "infrastructure_error"
    assert result["cleanup_ok"] is False
    with pytest.raises(RuntimeError):
        runner.run(FILES, "solve", [1])


def test_engine_disappearing_after_creation_retains_staging_and_blocks(tmp_path):
    engine = Path(fake_engine(tmp_path))
    engine.write_text(engine.read_text().replace('request=json.load(sys.stdin)',
                      'from pathlib import Path\n    Path(sys.argv[0]).unlink()\n    request=json.load(sys.stdin)'))
    runner = runner_type()(IMAGE, engine=str(engine))
    result = runner.run(FILES, "solve", [1])
    assert result['cleanup_ok'] is False
    assert result['status'] == 'infrastructure_error'
    assert Path(result['retained_staging_path']).exists()
    with pytest.raises(RuntimeError, match='cleanup'):
        runner.run(FILES, "solve", [1])


def test_engine_start_failure_is_not_a_candidate_failure(tmp_path):
    engine = Path(fake_engine(tmp_path))
    engine.write_text(engine.read_text().replace('request=json.load(sys.stdin)',
                      'print("daemon unavailable", file=sys.stderr); sys.exit(1)\n    request=json.load(sys.stdin)'))
    result = runner_type()(IMAGE, engine=str(engine)).run(FILES, "solve", [1])
    assert result["status"] == "infrastructure_error"
    assert result["cleanup_ok"] is True


def test_started_candidate_exit_one_is_a_candidate_failure(tmp_path):
    engine=Path(fake_engine(tmp_path))
    source=engine.read_text().replace('request=json.load(sys.stdin)','sys.exit(1)\n    request=json.load(sys.stdin)')
    source=source.replace('0001-01-01T00:00:00Z','2026-09-29T12:00:00Z').replace('"ExitCode":0','"ExitCode":1').replace('"Status":"created"','"Status":"exited"')
    engine.write_text(source)
    result=runner_type()(IMAGE,engine=str(engine)).run(FILES,'solve',[1])
    assert result['status']=='candidate_failure'
    assert result['cleanup_ok']


@pytest.mark.parametrize("name", ["../candidate.py", "/candidate.py", "_depverify_driver.py"])
def test_out_of_scope_staging_paths_are_rejected(tmp_path, name):
    runner = runner_type()(IMAGE, engine=fake_engine(tmp_path))
    with pytest.raises(ValueError):
        runner.run(FILES | {name: "pass"}, "solve", [1])


@pytest.fixture
def real_runner():
    image = os.environ.get("DEPVERIFY_DOCKER_TEST_IMAGE")
    if not image:
        pytest.skip("set DEPVERIFY_DOCKER_TEST_IMAGE to a pinned ARM64 image for real isolation fixtures")
    return runner_type()(image, record_dir=Path(os.environ.get("DEPVERIFY_RUN_DIR", "runs/m1/runner-fixtures")))


def test_real_candidate_json_and_fresh_state(real_runner):
    files = {"candidate.py": "counter = 0\ndef solve(x):\n    global counter\n    counter += 1\n    return [x, counter]\n"}
    for _ in range(2):
        result = real_runner.run(files, "solve", ["a"])
        assert result["status"] == "ok", result
        assert result["outputs"] == [["a", 1]]
        assert result["cleanup_ok"] is True


def test_real_infinite_loop_is_terminated_and_removed(real_runner):
    result = real_runner.run({"candidate.py": "def solve(x):\n    while True: pass\n"}, "solve", [1])
    assert result["status"] == "candidate_timeout", result
    assert result["elapsed_seconds"] <= 10
    assert result["cleanup_ok"] is True


def test_real_output_flood_is_bounded_and_removed(real_runner):
    result = real_runner.run({"candidate.py": "def solve(x):\n    while True: print('x' * 4096, flush=True)\n"}, "solve", [1])
    assert result["status"] == "output_limit", result
    assert result["captured_bytes"] <= 65536
    assert result["cleanup_ok"] is True


def test_real_subprocess_spawning_is_bounded(real_runner):
    source = "import subprocess\ndef solve(x):\n    jobs = []\n    try:\n        while True: jobs.append(subprocess.Popen(['sleep', '30']))\n    except OSError:\n        return len(jobs)\n"
    result = real_runner.run({"candidate.py": source}, "solve", [1])
    assert result["status"] in {"ok", "candidate_timeout"}, result
    if result["status"] == "ok":
        assert result["outputs"][0] < 32
    assert result["cleanup_ok"] is True


def test_real_network_access_is_denied(real_runner):
    source = "import socket\ndef solve(x):\n    try:\n        socket.create_connection(('1.1.1.1', 80), timeout=.3)\n        return 'CONNECTED'\n    except OSError:\n        return 'DENIED'\n"
    result = real_runner.run({"candidate.py": source}, "solve", [1])
    assert result["status"] == "ok", result
    assert result["outputs"] == ["DENIED"]


def test_real_home_file_is_not_available(real_runner, tmp_path):
    private = tmp_path / "private-home-canary"
    private.write_text("HOST_PRIVATE_CANARY")
    source = "from pathlib import Path\ndef solve(x):\n    try: return Path(x).read_text()\n    except OSError: return 'DENIED'\n"
    result = real_runner.run({"candidate.py": source}, "solve", [str(private)])
    assert result["outputs"] == ["DENIED"], result
    assert "HOST_PRIVATE_CANARY" not in result["stdout"]


def test_real_protected_file_write_is_denied(real_runner):
    source = "from pathlib import Path\ndef solve(x):\n    try:\n        Path('/work/support.py').write_text('CHANGED')\n        return 'WRITTEN'\n    except OSError: return 'DENIED'\n"
    result = real_runner.run(FILES | {"candidate.py": source}, "solve", [1])
    assert result["outputs"] == ["DENIED"], result
    assert result["cleanup_ok"] is True
