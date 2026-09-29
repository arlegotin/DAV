"""Milestone orchestration primitives, gates, and a serial auditable ledger."""

from collections.abc import Mapping
from contextlib import contextmanager
import fcntl
import math
import os
from pathlib import Path
import platform
from dataclasses import replace
from importlib.metadata import version
import tomllib

from .records import CHECK_IDS, GateResult, Proposal, Task, append_event, canonical_json, from_dict, proposal_key, read_events, read_json, sha256_bytes, to_dict, write_json_atomic

_STAGE_MODEL_CAPS = {"M0": 0., "M1": 900., "M2": 3600., "M3": 14400., "M4": 10800., "M5": 7200., "M6": 0.}
_RETRY_STATUSES = {"infrastructure_error", "model_timeout", "interrupted"}
REPO_ROOT = Path(__file__).resolve().parents[2]
FAKE_ENVIRONMENT = {"schema_version": 1, "runner": "fake-v1", "model": "fake-v1"}
FAKE_CHECK_VERSIONS = dict.fromkeys(CHECK_IDS, "fake-v1")


class BudgetStop(RuntimeError):
    """Checkpoint the stage before launching additional actual work."""


def _nonnegative(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("work values must be finite and nonnegative")
    return float(value)


@contextmanager
def _lock(path: Path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_name(path.name + ".lock").open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        yield


def _validate_limits(limits):
    if not isinstance(limits, Mapping) or set(limits) != {"total_seconds", "stage_seconds", "per_call_seconds"}:
        raise ValueError("invalid work-limit schema")
    caps = {"model": 180., "execution": 10.}
    if set(limits["per_call_seconds"]) != set(caps):
        raise ValueError("model and execution timeouts are required")
    for kind, value in limits["per_call_seconds"].items():
        if not 0 < _nonnegative(value) <= caps[kind]:
            raise ValueError("timeout exceeds the execution envelope")
    if "model" not in limits["total_seconds"] or _nonnegative(limits["total_seconds"]["model"]) > 43200.:
        raise ValueError("invalid total model budget")
    for kind, value in limits["total_seconds"].items():
        if kind not in caps:
            raise ValueError("unknown work dimension")
        _nonnegative(value)
    for stage, stage_caps in limits["stage_seconds"].items():
        if stage not in _STAGE_MODEL_CAPS or not isinstance(stage_caps, Mapping):
            raise ValueError("unknown stage")
        for kind, value in stage_caps.items():
            if kind not in caps or (kind == "model" and _nonnegative(value) > _STAGE_MODEL_CAPS[stage]):
                raise ValueError("invalid stage budget")
            _nonnegative(value)


def _state(events):
    attempts, caps, revisions, interrupted = {}, None, {}, []
    for event in events:
        kind = event.get("type")
        if kind == "limits":
            if caps is not None or event.get("event_id") != "limits":
                raise ValueError("duplicate work limits")
            caps = event["limits"]
            _validate_limits(caps)
            if event.get("limits_hash") != sha256_bytes(canonical_json(caps)):
                raise ValueError("corrupt limit identity")
        elif kind == "reserve":
            if caps is None:
                raise ValueError("reservation without limits")
            attempt_id, stage, work_kind = event["attempt_id"], event["stage"], event["work_kind"]
            if not isinstance(attempt_id, str) or not attempt_id or attempt_id in attempts or event["event_id"] != "reserve:" + attempt_id:
                raise ValueError("invalid reservation identity")
            if stage not in _STAGE_MODEL_CAPS or work_kind not in ("model", "execution"):
                raise ValueError("invalid reservation scope")
            allowance = _nonnegative(event["allowance_seconds"])
            if allowance != caps["per_call_seconds"][work_kind]:
                raise ValueError("reservation must cover its full timeout")
            attempts[attempt_id] = {"reservation_id": event["event_id"], "stage": stage, "work_kind": work_kind,
                                    "allowance_seconds": allowance, "status": "pending", "actual_seconds": None}
        elif kind == "settle":
            reservation = event["reservation_id"]
            attempt_id = reservation.removeprefix("reserve:")
            if attempt_id not in attempts or attempts[attempt_id]["status"] != "pending" or event["event_id"] != "settle:" + reservation:
                raise ValueError("invalid or repeated settlement")
            actual, status = _nonnegative(event["actual_seconds"]), event["status"]
            if not isinstance(status, str) or not status or status == "pending":
                raise ValueError("invalid settlement status")
            attempts[attempt_id].update(actual_seconds=actual, status=status)
        elif kind == "revision":
            revision = event["kind"]
            if revision not in ("pilot", "mechanism") or revision in revisions:
                raise ValueError("revision allowance exhausted")
            revisions[revision] = event["reason"]
        elif kind == "interrupted_tail":
            interrupted.append(event["artifact"])
        else:
            raise ValueError("unknown ledger event")
    actual, reserved, by_stage = {"model": 0., "execution": 0.}, {"model": 0., "execution": 0.}, {}
    for attempt_id, attempt in attempts.items():
        amount = attempt["allowance_seconds"] if attempt["status"] == "pending" else attempt["actual_seconds"]
        bucket = reserved if attempt["status"] == "pending" else actual
        bucket[attempt["work_kind"]] += amount
        by_stage.setdefault(attempt["stage"], {"model": 0., "execution": 0.})[attempt["work_kind"]] += amount
        attempt["released_seconds"] = 0. if attempt["status"] == "pending" else max(0., attempt["allowance_seconds"] - amount)
        attempt["retry_allowed"] = attempt["status"] in _RETRY_STATUSES and "::retry" not in attempt_id and attempt_id + "::retry1" not in attempts
    return {"attempts": attempts, "limits": caps, "revisions": revisions, "interrupted_artifacts": interrupted,
            "model_seconds": actual["model"], "reserved_model_seconds": reserved["model"],
            "execution_seconds": actual["execution"], "reserved_execution_seconds": reserved["execution"],
            "accounted_model_seconds": actual["model"] + reserved["model"],
            "accounted_execution_seconds": actual["execution"] + reserved["execution"], "stage_accounted_seconds": by_stage}


def reserve(ledger_path: Path, *, attempt_id: str, stage: str, work_kind: str, allowance_seconds: float, limits: dict) -> str:
    path = Path(ledger_path)
    _validate_limits(limits)
    if not isinstance(attempt_id, str) or not attempt_id or stage not in _STAGE_MODEL_CAPS or work_kind not in ("model", "execution"):
        raise ValueError("invalid work identity")
    allowance = _nonnegative(allowance_seconds)
    if allowance != limits["per_call_seconds"][work_kind]:
        raise ValueError("reserve the full configured timeout")
    if stage in ("M0", "M6"):
        raise BudgetStop("this stage permits no model or candidate execution")
    with _lock(path):
        state = _state(read_events(path))
        if state["limits"] is not None and canonical_json(state["limits"]) != canonical_json(limits):
            raise ValueError("limits cannot reset an existing ledger")
        if attempt_id in state["attempts"]:
            raise ValueError("attempt already reserved; reconcile instead of launching again")
        if "::retry" in attempt_id:
            base, suffix = attempt_id.split("::retry", 1)
            original = state["attempts"].get(base)
            if suffix != "1" or original is None or not original["retry_allowed"] or original["stage"] != stage or original["work_kind"] != work_kind:
                raise ValueError("only one matching infrastructure retry is allowed")
        if any(a["actual_seconds"] is not None and a["actual_seconds"] > a["allowance_seconds"] for a in state["attempts"].values()):
            raise BudgetStop("an actual overrun requires investigation before expansion")
        if work_kind == "model" and "model" not in limits["stage_seconds"].get(stage, {}):
            raise ValueError("model work requires a declared stage budget")
        total = state["accounted_" + work_kind + "_seconds"]
        stage_total = state["stage_accounted_seconds"].get(stage, {}).get(work_kind, 0.)
        total_cap = limits["total_seconds"].get(work_kind)
        stage_cap = limits["stage_seconds"].get(stage, {}).get(work_kind)
        if (total_cap is not None and total + allowance > total_cap) or (stage_cap is not None and stage_total + allowance > stage_cap):
            raise BudgetStop("insufficient allowance; checkpoint the stage")
        if state["limits"] is None:
            append_event(path, {"event_id": "limits", "type": "limits", "limits": limits,
                                "limits_hash": sha256_bytes(canonical_json(limits))})
        reservation_id = "reserve:" + attempt_id
        append_event(path, {"event_id": reservation_id, "type": "reserve", "attempt_id": attempt_id,
                            "stage": stage, "work_kind": work_kind, "allowance_seconds": allowance})
        return reservation_id


def settle(ledger_path: Path, *, reservation_id: str, actual_seconds: float, status: str) -> None:
    path, actual = Path(ledger_path), _nonnegative(actual_seconds)
    if not isinstance(status, str) or not status or status == "pending":
        raise ValueError("invalid settlement status")
    with _lock(path):
        state = _state(read_events(path))
        attempt = next((a for a in state["attempts"].values() if a["reservation_id"] == reservation_id), None)
        if attempt is None:
            raise ValueError("unknown reservation")
        if attempt["status"] != "pending":
            if attempt["status"] == status and attempt["actual_seconds"] == actual:
                return
            raise ValueError("conflicting settlement")
        append_event(path, {"event_id": "settle:" + reservation_id, "type": "settle", "reservation_id": reservation_id,
                            "actual_seconds": actual, "status": status})


def resume_attempts(ledger_path: Path) -> dict:
    path = Path(ledger_path)
    with _lock(path):
        if path.exists():
            data = path.read_bytes()
            if data and not data.endswith(b"\n"):
                boundary = data.rfind(b"\n") + 1
                prefix, tail = data[:boundary], data[boundary:]
                # A corrupt completed prefix is never guessed or discarded.
                if prefix:
                    for line in prefix.splitlines():
                        from .records import parse_json
                        parse_json(line.decode("utf-8"))
                digest = sha256_bytes(tail)
                archive = path.with_name(path.stem + ".partial-" + digest + ".bin")
                if archive.exists() and archive.read_bytes() != tail:
                    raise ValueError("conflicting interrupted artifact")
                if not archive.exists():
                    with archive.open("xb") as stream:
                        stream.write(tail)
                        stream.flush()
                        os.fsync(stream.fileno())
                with path.open("r+b") as stream:
                    stream.truncate(boundary)
                    stream.flush()
                    os.fsync(stream.fileno())
                append_event(path, {"event_id": "interrupted:" + digest, "type": "interrupted_tail", "artifact": archive.name})
        return _state(read_events(path))


def record_revision(ledger_path: Path, *, kind: str, reason: str) -> None:
    if kind not in ("pilot", "mechanism") or not isinstance(reason, str) or not reason:
        raise ValueError("a permitted revision requires a documented reason")
    path = Path(ledger_path)
    with _lock(path):
        state = _state(read_events(path))
        if kind in state["revisions"]:
            if state["revisions"][kind] == reason:
                return
            raise ValueError("revision allowance exhausted")
        append_event(path, {"event_id": "revision:" + kind, "type": "revision", "kind": kind, "reason": reason})


def _criteria_pass(criteria):
    return bool(criteria) and all(value is True or isinstance(value, Mapping) and value.get("passed") is True for value in criteria.values())


def write_gate(path: Path, result: GateResult) -> None:
    if result.status == "GO" and not _criteria_pass(result.criteria):
        raise ValueError("GO requires every recorded criterion to pass")
    path = Path(path)
    with _lock(path):
        history = path.with_name(path.stem + ".history")
        records = [to_dict(result)]
        if path.exists():
            records.append(to_dict(from_dict(GateResult, read_json(path))))
        for record in records:
            archive = history / (sha256_bytes(canonical_json(record)) + ".json")
            if archive.exists():
                if read_json(archive) != record:
                    raise ValueError("gate archive changed")
            else:
                write_json_atomic(archive, record)
        write_json_atomic(path, to_dict(result))


def require_gate(gate_path: Path, *, stage: str, expected_hashes: dict) -> GateResult:
    if not expected_hashes:
        raise ValueError("current artifact identities are required")
    try:
        gate = from_dict(GateResult, read_json(gate_path))
    except (OSError, ValueError) as exc:
        raise ValueError("missing or corrupt prerequisite gate") from exc
    if gate.stage != stage or gate.status != "GO" or not _criteria_pass(gate.criteria):
        raise ValueError("prerequisite gate is not GO")
    if any(gate.artifact_hashes.get(key) != digest for key, digest in expected_hashes.items()):
        raise ValueError("prerequisite gate has stale artifacts")
    return gate


def load_config(path: Path) -> dict:
    with Path(path).open("rb") as stream:
        config = tomllib.load(stream)
    if set(config) != {"experiment", "limits", "storage", "budgets", "objective", "revisions"} or config["experiment"] != {"schema_version": 1}:
        raise ValueError("unknown configuration field or schema; no gate bypass exists")
    limit_caps = {"resident_models": 1, "concurrent_model_requests": 1, "input_tokens": 3072,
                  "proposal_output_tokens": 512, "review_output_tokens": 128, "context_tokens": 4096,
                  "replacement_bytes": 65536, "acquisitions": 4, "model_call_seconds": 180, "candidate_seconds": 10,
                  "candidate_output_bytes": 65536, "candidate_cpus": 1, "candidate_memory_mib": 512, "candidate_pids": 32,
                  "resource_reserve_gib": 8, "resource_reserve_fraction": .25, "planning_margin": 1.5}
    if set(config["limits"]) != set(limit_caps):
        raise ValueError("invalid limit configuration")
    for name, value in config["limits"].items():
        if _nonnegative(value) != limit_caps[name]:
            raise ValueError("default execution limits changed; revise explicitly before experimental freeze")
    if config["objective"] != {"wrong_accept": 20, "defer": 5} or config["revisions"] != {"pilot": 1, "mechanism": 1}:
        raise ValueError("primary objective or revision allowances changed")
    if config["storage"] != {"planning_margin": 1.5, "reserve_bytes": 1073741824}:
        raise ValueError("invalid per-filesystem storage budget")
    if set(config["budgets"]) != {"model_total_seconds", "stage_model_seconds"}:
        raise ValueError("invalid budget configuration")
    if _nonnegative(config["budgets"]["model_total_seconds"]) != 43200. or config["budgets"]["stage_model_seconds"] != _STAGE_MODEL_CAPS:
        raise ValueError("research budgets changed")
    return config


def implementation_hashes(config_path: Path | None = None) -> dict:
    paths = [*REPO_ROOT.joinpath("src/depverify").glob("*.py"), *REPO_ROOT.joinpath("tests").glob("*.py"),
             REPO_ROOT / "pyproject.toml", REPO_ROOT / "requirements.lock"]
    paths.extend(p for folder in (REPO_ROOT / "prompts", REPO_ROOT / "bench") if folder.exists()
                 for p in folder.rglob("*") if p.is_file() and p.suffix in {".txt", ".py", ".json", ".jsonl"})
    hashes = {path.relative_to(REPO_ROOT).as_posix(): sha256_bytes(path.read_bytes()) for path in sorted(paths)}
    return {"code": sha256_bytes(canonical_json(hashes)),
            "config": sha256_bytes(Path(config_path or REPO_ROOT / "config.toml").read_bytes())}


def fake_actor_metadata(task: Task, replacement: str) -> dict:
    return {"model_revision": "fake-v1", "tokenizer_revision": "fake-v1", "seed": 1,
            "prompt_hash": sha256_bytes(canonical_json(to_dict(task))),
            "environment_hash": sha256_bytes(canonical_json(FAKE_ENVIRONMENT)),
            "input_tokens": 10, "output_tokens": 10, "elapsed_seconds": 8.,
            "timed_out": False, "cache_hit": False, "sampling_settings": {"temperature": .2},
            "attempt_id": "fake-actor:" + task.episode_id, "fake": True, "cost_regime": "synthetic"}


def run_fake_episode(task: Task, replacement: str, evidence: Mapping, policy, parent: Path) -> tuple:
    from .evaluate import replay_episode
    from .tasks import apply_or_defer, materialize, preflight
    root = materialize(task, parent)
    status, manifest = preflight(task, replacement, root)
    key = proposal_key(task, replacement, FAKE_ENVIRONMENT, FAKE_CHECK_VERSIONS)
    proposal = Proposal(task.episode_id, key, replacement, status, fake_actor_metadata(task, replacement), manifest["elapsed_seconds"])
    decision = replay_episode(proposal, "unknown_lineage", frozenset(CHECK_IDS), policy, evidence,
                               policy_hash=sha256_bytes(canonical_json({"fake_policy": getattr(policy, "__name__", "callback")})))
    applied = apply_or_defer(task, proposal, decision.action, root,
                            {"proposal_key": key, "environment": FAKE_ENVIRONMENT, "check_versions": FAKE_CHECK_VERSIONS})
    if decision.action == "ACCEPT" and applied["status"] not in ("applied", "already_applied"):
        decision = replace(decision, action="DEFER", status=applied["status"])
    return proposal, replace(decision, wrapper_seconds=applied["wrapper_seconds"])


def doctor_fake(run_dir: Path, config_path: Path) -> dict:
    import sys
    config = load_config(config_path)
    output = {"schema_version": 1, "mode": "fake", "benchmark_eligible": False, "python_version": platform.python_version(),
              "dependencies": {name: version(name) for name in ("numpy", "scipy", "pytest")},
              "artifact_hashes": implementation_hashes(config_path), "limits": config["limits"],
              "model_calls": 0, "candidate_executions": 0, "mlx_loaded": any(n.startswith("mlx") for n in sys.modules),
              "container_engine_used": False}
    path = Path(run_dir) / "doctor.json"
    write_json_atomic(path.parent / "doctor.history" / (sha256_bytes(canonical_json(output)) + ".json"), output)
    write_json_atomic(path, output)
    return output
