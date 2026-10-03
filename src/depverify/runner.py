"""Inert fake runner and a bounded, public-files-only container runner."""

from collections.abc import Mapping, Sequence
import math
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import shutil
import subprocess
import tempfile
import time
import uuid

from .records import canonical_json, parse_json, sha256_bytes, write_json_atomic


class FakeRunner:
    def __init__(self, responses: Mapping[str, dict]):
        self._responses = parse_json(canonical_json(responses).decode("utf-8"))
        self._invocations = 0

    def run(self, proposal_key: str, inputs: Sequence[object]) -> dict:
        if proposal_key not in self._responses:
            raise ValueError("no registered fake response")
        response = parse_json(canonical_json(self._responses[proposal_key]).decode("utf-8"))
        if not isinstance(response, dict) or not {"status", "inputs", "outputs", "elapsed_seconds"}.issubset(response):
            raise ValueError("incomplete fake response")
        if canonical_json(response["inputs"]) != canonical_json(inputs):
            raise ValueError("fake response requires exact registered inputs")
        if not isinstance(response["outputs"], list) or len(response["outputs"]) != len(inputs):
            raise ValueError("fake response input/output count mismatch")
        elapsed = response["elapsed_seconds"]
        if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError("invalid fake execution cost")
        self._invocations += 1
        return response | {"fake": True, "invocation": self._invocations}


def _pinned_image(image):
    if not isinstance(image, str) or not re.fullmatch(r"[a-zA-Z0-9./:_-]+@sha256:[0-9a-f]{64}", image):
        raise ValueError("a digest-pinned image is required")
    return image


def runner_environment(image, *, engine="docker"):
    """Trusted read-only probes; no candidate code is invoked here."""
    _pinned_image(image)
    result = subprocess.run([engine, "image", "inspect", image], capture_output=True, timeout=10, check=True)
    info = parse_json(result.stdout.decode())[0]
    if info["Architecture"] != "arm64" or info["Os"] != "linux":
        raise ValueError("the execution image must be Linux ARM64")
    version = subprocess.run([engine, "version", "--format", "{{json .}}"], capture_output=True, timeout=10, check=True)
    memory = subprocess.run([engine, "info", "--format", "{{.MemTotal}}"], capture_output=True, timeout=10, check=True)
    return {"image": image, "image_id": info["Id"], "architecture": info["Architecture"],
            "os": info["Os"], "engine": parse_json(version.stdout.decode()),
            "engine_memory_bytes": int(memory.stdout.strip()),
            "driver_hash": sha256_bytes(Path(__file__).with_name("_container_driver.py").read_bytes())}


def _capture(argv, *, deadline, limit, payload=None):
    """Drain both pipes without unbounded buffering; stop the CLI at the cap."""
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE if payload is not None else subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    streams = {"stdout": bytearray(), "stderr": bytearray()}
    status, offset = "complete", 0
    with selectors.DefaultSelector() as selector:
        for name in streams:
            pipe = getattr(proc, name)
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ, name)
        if payload is not None:
            os.set_blocking(proc.stdin.fileno(), False)
            selector.register(proc.stdin, selectors.EVENT_WRITE, "stdin")
        try:
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    status = "timeout"
                    break
                for key, _ in selector.select(min(.05, remaining)):
                    pipe, name = key.fileobj, key.data
                    if name == "stdin":
                        try:
                            offset += os.write(pipe.fileno(), payload[offset:offset + 8192])
                        except BrokenPipeError:
                            offset = len(payload)
                        if offset >= len(payload):
                            selector.unregister(pipe)
                            pipe.close()
                    else:
                        capacity = limit - sum(map(len, streams.values()))
                        # One extra byte detects overflow; it is never retained.
                        chunk = os.read(pipe.fileno(), min(8192, capacity + 1))
                        if not chunk:
                            selector.unregister(pipe)
                            pipe.close()
                        else:
                            streams[name].extend(chunk[:capacity])
                            if len(chunk) > capacity:
                                status = "output_limit"
                                break
                if status != "complete":
                    break
            if status != "complete" or proc.poll() is None:
                if status == "complete":
                    try:
                        proc.wait(timeout=max(.001, deadline - time.monotonic()))
                    except subprocess.TimeoutExpired:
                        status = "timeout"
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=1)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=1)
            for pipe in (proc.stdin, proc.stdout, proc.stderr):
                if pipe is not None and not pipe.closed:
                    pipe.close()
    return {"stream_status": status, "exit_code": proc.returncode,
            **{name: bytes(data).decode("utf-8", errors="replace") for name, data in streams.items()},
            "captured_bytes": sum(map(len, streams.values()))}


class ContainerRunner:
    def __init__(self, image, *, engine="docker", timeout=10., output_limit=65536, record_dir=None,
                 ledger=None, limits=None, stage="M1"):
        self.image = _pinned_image(image)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 2 < timeout <= 10:
            raise ValueError("runner timeout must leave cleanup time and not exceed ten seconds")
        if isinstance(output_limit, bool) or not isinstance(output_limit, int) or not 0 < output_limit <= 65536:
            raise ValueError("invalid output cap")
        self.engine, self.timeout, self.output_limit = engine, timeout, output_limit
        self.record_dir = Path(record_dir) if record_dir is not None else None
        self.ledger = Path(ledger) if ledger is not None else (self.record_dir / "budget.jsonl" if self.record_dir else None)
        self.limits = limits or {"total_seconds": {"model": 43200.}, "stage_seconds": {"M1": {"model": 900.}},
                                 "per_call_seconds": {"model": 180., "execution": 10.}}
        self.stage, self._blocked = stage, False

    def run(self, files, entry_point, inputs):
        if self._blocked:
            raise RuntimeError("unverified container cleanup blocks further execution")
        if not isinstance(files, dict) or "candidate.py" not in files or not isinstance(inputs, list):
            raise ValueError("explicit candidate/public files and input values are required")
        if not isinstance(entry_point, str) or not entry_point.isidentifier():
            raise ValueError("invalid entry point")
        for name, source in files.items():
            path = PurePosixPath(name)
            if (path.is_absolute() or any(part in ("..", ".") for part in path.parts)
                    or name != str(path) or "\\" in name or name == "_depverify_driver.py"
                    or not isinstance(source, str) or len(source.encode()) > 65536):
                raise ValueError("out-of-scope public staging path or size")
        payload = canonical_json({"entry_point": entry_point, "inputs": inputs})
        if len(payload) > 1048576:
            raise ValueError("input values exceed the bounded protocol")
        attempt = uuid.uuid4().hex
        reservation = None
        if self.ledger:
            from .pipeline import reserve
            reservation = reserve(self.ledger, attempt_id="container-" + attempt, stage=self.stage,
                                  work_kind="execution", allowance_seconds=10., limits=self.limits)
        started = time.monotonic()
        deadline = started + self.timeout
        name = "depverify-" + attempt
        staging = Path(tempfile.mkdtemp(prefix="depverify-public-"))
        cid, created, cleanup_ok = None, False, True
        staged = files | {"_depverify_driver.py": Path(__file__).with_name("_container_driver.py").read_text()}
        result = {"status": "infrastructure_error", "outputs": [], "stdout": "", "stderr": "",
                  "exit_code": None, "captured_bytes": 0,
                  "container_name": name, "staged_files": {p: sha256_bytes(s.encode()) for p, s in staged.items()}}
        try:
            for path, source in staged.items():
                target = staging / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source)
                target.chmod(0o444)
            # Container UID 65534 must be able to traverse the fresh mount.
            for directory in [staging, *(p for p in staging.rglob("*") if p.is_dir())]:
                directory.chmod(0o555)
            argv = [self.engine, "create", "--name", name, "--pull=never", "--platform", "linux/arm64",
                    "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges=true",
                    "--user", "65534:65534", "--cpus", "1", "--memory", "512m", "--memory-swap", "512m",
                    "--pids-limit", "32", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m", "--log-driver", "none",
                    "--mount", f"type=bind,src={staging},dst=/work,readonly", "--workdir", "/work", "--interactive",
                    self.image, "python", "-I", "-B", "/work/_depverify_driver.py"]
            created = True  # Track the name even if create dies before returning a CID.
            try:
                creation = _capture(argv, deadline=deadline - 2., limit=self.output_limit)
            except FileNotFoundError:
                # Popen never launched the create command; no container can exist.
                created = False
                raise
            if creation["stream_status"] != "complete" or creation["exit_code"] != 0:
                result.update({k: creation[k] for k in ("stdout", "stderr", "exit_code", "captured_bytes")})
            else:
                cid = creation["stdout"].strip()
                if not re.fullmatch("[a-f0-9]{64}", cid):
                    raise ValueError("engine returned an invalid container ID")
                capture = _capture([self.engine, "start", "--attach", "--interactive", cid],
                                   deadline=deadline - 2., limit=self.output_limit, payload=payload)
                result.update({k: capture[k] for k in ("stdout", "stderr", "exit_code", "captured_bytes")})
                if capture["stream_status"] == "timeout":
                    result["status"] = "candidate_timeout"
                elif capture["stream_status"] == "output_limit":
                    result["status"] = "output_limit"
                else:
                    try:
                        response = parse_json(capture["stdout"])
                        if response.get("status") == "ok" and capture["exit_code"] == 0:
                            if not isinstance(response["outputs"], list) or len(response["outputs"]) != len(inputs):
                                raise ValueError("candidate response count mismatch")
                            result.update(status="ok", outputs=response["outputs"])
                            if 'input_mutated' in response:
                                flags=response['input_mutated']
                                if (not isinstance(flags,list) or len(flags)!=len(inputs) or
                                        any(type(flag) is not bool for flag in flags)):
                                    raise ValueError('invalid input mutation observations')
                                result['input_mutated']=flags
                        elif response.get("status") == "candidate_failure":
                            result["status"] = "candidate_failure"
                        else:
                            result["status"] = "infrastructure_error" if capture["exit_code"] == 125 else "candidate_failure"
                    except (ValueError, KeyError, AttributeError, TypeError):
                        result["status"] = "infrastructure_error"
                    if result['status']=='infrastructure_error':
                        state_result=_capture([self.engine,'container','inspect',cid],deadline=deadline-2.,limit=4096)
                        try:
                            state=parse_json(state_result['stdout'])[0]['State']
                            result['execution_state']=state
                            if (state_result['exit_code']==0 and state['Status']=='exited' and
                                    not state.get('Error') and state['StartedAt']!='0001-01-01T00:00:00Z'):
                                result['status']='candidate_failure'
                        except (ValueError,KeyError,TypeError,IndexError):pass
        except (OSError, ValueError) as exc:
            result["error_type"] = type(exc).__name__
        finally:
            if created:
                try:
                    removal = _capture([self.engine, "rm", "--force", name], deadline=deadline - .5, limit=4096)
                    inspection = _capture([self.engine, "ps", "--all", "--filter", "name=^/" + name + "$",
                                           "--format", "{{.ID}}"], deadline=deadline, limit=4096)
                    cleanup_ok = (removal["stream_status"] == "complete" and inspection["stream_status"] == "complete"
                                  and inspection["exit_code"] == 0 and not inspection["stdout"].strip())
                except OSError:
                    cleanup_ok = False
            result.update(container_id=cid, cleanup_ok=cleanup_ok, elapsed_seconds=time.monotonic() - started)
            if not cleanup_ok:
                self._blocked = True
                result["status"] = "infrastructure_error"
                result["retained_staging_path"] = str(staging)
            else:
                for directory in [staging, *(p for p in staging.rglob("*") if p.is_dir())]:
                    directory.chmod(0o755)
                shutil.rmtree(staging)
            if self.record_dir:
                write_json_atomic(self.record_dir / (attempt + ".json"), result | {"image": self.image,
                                  "input_hash": sha256_bytes(payload), "entry_point": entry_point})
            if reservation:
                from .pipeline import settle
                settle(self.ledger, reservation_id=reservation, actual_seconds=result["elapsed_seconds"], status=result["status"])
        return result
