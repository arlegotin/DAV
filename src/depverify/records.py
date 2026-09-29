"""Strict records, canonical identities, and durable local JSON events."""

from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from types import MappingProxyType
from typing import Literal

Verdict = Literal["PASS", "FAIL", "UNKNOWN"]
TerminalAction = Literal["ACCEPT", "DEFER"]
CheckId = Literal["R1", "R2", "T", "D"]
Lineage = Literal["same_lineage", "distinct_lineage", "unknown_lineage"]
History = tuple[str | None, str | None, str | None, str | None]
CHECK_IDS = ("R1", "R2", "T", "D")
VERDICTS = ("PASS", "FAIL", "UNKNOWN")
LINEAGES = ("same_lineage", "distinct_lineage", "unknown_lineage")
EMPTY_HISTORY: History = (None, None, None, None)
_PRIVATE_KEYS = {"label", "Y", "hidden_tests", "reference_implementation", "condition",
                 "hidden_expected_outputs", "injected_condition"}


def _json_value(value):
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: _json_value(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        if any(not isinstance(k, str) for k in value):
            raise ValueError("JSON keys must be strings")
        return {k: _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite JSON number")
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise ValueError(f"unsupported JSON value: {type(value).__name__}")


def canonical_json(value: object) -> bytes:
    return json.dumps(_json_value(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _freeze(value):
    value = _json_value(value)
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


def _text(value, name, *, empty=False):
    if not isinstance(value, str) or (not empty and not value):
        raise ValueError(f"{name} must be a string")


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and nonnegative")


def _integer(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")


def _hash(value, name):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{name} must be a SHA256 hex digest")


def _schema(record):
    if type(record.schema_version) is not int or record.schema_version != 1:
        raise ValueError("unsupported record schema")


def _mapping(record, name):
    value = getattr(record, name)
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    object.__setattr__(record, name, _freeze(value))


def _no_private(value):
    if isinstance(value, Mapping):
        if _PRIVATE_KEYS.intersection(value):
            raise ValueError("private material cannot enter a public Task")
        for item in value.values():
            _no_private(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _no_private(item)


def _metadata(value, required, *, actor=False):
    if not required.issubset(value):
        raise ValueError(f"missing metadata: {sorted(required.difference(value))}")
    for name in ("model_revision", "tokenizer_revision"):
        _text(value[name], name)
    for name in ("prompt_hash", "environment_hash"):
        _hash(value[name], name)
    for name in ("input_tokens", "output_tokens", "seed" if actor else "check_seed"):
        _integer(value[name], name)
    for name in ("timed_out", "cache_hit"):
        if type(value[name]) is not bool:
            raise ValueError(f"{name} must be boolean")
    if actor:
        _number(value["elapsed_seconds"], "elapsed_seconds")
        _text(value["attempt_id"], "attempt_id")
        if not isinstance(value["sampling_settings"], Mapping):
            raise ValueError("sampling_settings must be an object")
    else:
        _text(value["check_version"], "check_version")
        _hash(value["machine_profile_hash"], "machine_profile_hash")
        for name in ("source_hashes", "source_versions"):
            if not isinstance(value[name], Mapping):
                raise ValueError(f"{name} must be an object")
        for source_hash in value["source_hashes"].values():
            _hash(source_hash, "source_hash")
        if not isinstance(value["attempt_ids"], (tuple, list)) or not value["attempt_ids"]:
            raise ValueError("attempt_ids must be a nonempty sequence")
        for item in value["attempt_ids"]:
            _text(item, "attempt_id")


@dataclass(frozen=True)
class Task:
    episode_id: str
    root_group_id: str
    split: str
    task_class: str
    contract: str
    editable_path: str
    entry_point: str
    base_files: dict[str, str]
    public_tests: tuple[dict, ...]
    source_manifest: dict
    schema_version: int = 1

    def __post_init__(self):
        _schema(self)
        for name in ("episode_id", "root_group_id", "split", "task_class", "contract", "editable_path", "entry_point"):
            _text(getattr(self, name), name)
        _mapping(self, "base_files")
        if self.editable_path not in self.base_files or not all(isinstance(v, str) for v in self.base_files.values()):
            raise ValueError("base files must contain the editable Python source")
        if not isinstance(self.public_tests, (tuple, list)):
            raise ValueError("public_tests must be a sequence")
        object.__setattr__(self, "public_tests", _freeze(self.public_tests))
        _mapping(self, "source_manifest")
        _no_private(self.source_manifest)


@dataclass(frozen=True)
class Proposal:
    episode_id: str
    proposal_key: str
    replacement: str
    status: str
    actor: dict
    preflight_seconds: float
    schema_version: int = 1

    def __post_init__(self):
        _schema(self)
        _text(self.episode_id, "episode_id")
        _hash(self.proposal_key, "proposal_key")
        _text(self.replacement, "replacement", empty=True)
        _text(self.status, "status")
        _number(self.preflight_seconds, "preflight_seconds")
        _mapping(self, "actor")
        _metadata(self.actor, {"model_revision", "tokenizer_revision", "seed", "prompt_hash", "environment_hash",
                               "input_tokens", "output_tokens", "elapsed_seconds", "timed_out", "cache_hit",
                               "sampling_settings", "attempt_id"}, actor=True)


@dataclass(frozen=True)
class CheckResult:
    proposal_key: str
    check_id: str
    verdict: str
    status: str
    reason: str
    elapsed_seconds: float
    metadata: dict
    schema_version: int = 1

    def __post_init__(self):
        _schema(self)
        _hash(self.proposal_key, "proposal_key")
        if self.check_id not in CHECK_IDS or self.verdict not in VERDICTS:
            raise ValueError("invalid check ID or verdict")
        _text(self.status, "status")
        _text(self.reason, "reason", empty=True)
        _number(self.elapsed_seconds, "elapsed_seconds")
        _mapping(self, "metadata")
        _metadata(self.metadata, {"model_revision", "tokenizer_revision", "check_version", "check_seed",
                                  "prompt_hash", "source_hashes", "source_versions", "input_tokens", "output_tokens",
                                  "timed_out", "cache_hit", "machine_profile_hash", "environment_hash", "attempt_ids"})
        if self.status in {"format_error", "truncated", "input_over_budget", "unavailable", "model_timeout",
                           "infrastructure_error", "refusal"} and self.verdict != "UNKNOWN":
            raise ValueError("failed acquisition must be UNKNOWN")


@dataclass(frozen=True)
class Decision:
    proposal_key: str
    policy_hash: str
    history: tuple[tuple[str, str], ...]
    action: str
    status: str
    selected_check_seconds: float
    controller_seconds: float
    wrapper_seconds: float
    schema_version: int = 1

    def __post_init__(self):
        _schema(self)
        _hash(self.proposal_key, "proposal_key")
        _hash(self.policy_hash, "policy_hash")
        if self.action not in ("ACCEPT", "DEFER"):
            raise ValueError("invalid terminal decision")
        _text(self.status, "status")
        for name in ("selected_check_seconds", "controller_seconds", "wrapper_seconds"):
            _number(getattr(self, name), name)
        object.__setattr__(self, "history", _freeze(self.history))
        seen = set()
        for entry in self.history:
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise ValueError("history entries must be check/verdict pairs")
            check, verdict = entry
            if check not in CHECK_IDS or verdict not in VERDICTS or check in seen:
                raise ValueError("invalid or duplicate acquired check")
            seen.add(check)
        if ("T", "FAIL") in self.history and self.action == "ACCEPT":
            raise ValueError("acquired public failure vetoes acceptance")


@dataclass(frozen=True)
class GateResult:
    stage: str
    status: str
    recorded_at: str
    artifact_hashes: dict
    criteria: dict
    reasons: tuple[str, ...]
    evidence_paths: tuple[str, ...]
    budget_snapshot: dict
    schema_version: int = 1

    def __post_init__(self):
        _schema(self)
        if self.stage not in tuple(f"M{i}" for i in range(7)) or self.status not in ("GO", "NO_GO", "BLOCKED", "INCONCLUSIVE"):
            raise ValueError("invalid gate stage or status")
        timestamp = datetime.fromisoformat(self.recorded_at.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError("gate timestamp requires a timezone")
        for name in ("artifact_hashes", "criteria", "budget_snapshot"):
            _mapping(self, name)
        for digest in self.artifact_hashes.values():
            _hash(digest, "artifact_hash")
        for name in ("reasons", "evidence_paths"):
            value = getattr(self, name)
            if not isinstance(value, (tuple, list)) or any(not isinstance(v, str) for v in value):
                raise ValueError(f"{name} must be a sequence of strings")
            object.__setattr__(self, name, tuple(value))


def to_dict(record) -> dict:
    if type(record) not in (Task, Proposal, CheckResult, Decision, GateResult):
        raise ValueError("unknown record type")
    return _json_value(record)


def from_dict(record_type, value: dict):
    if record_type not in (Task, Proposal, CheckResult, Decision, GateResult) or not isinstance(value, dict):
        raise ValueError("unknown record type or invalid object")
    names = {f.name for f in fields(record_type)}
    if set(value) != names:
        raise ValueError("record fields do not match schema")
    return record_type(**value)


def proposal_key(task: Task, replacement: str, environment: dict, check_versions: dict) -> str:
    return sha256_bytes(canonical_json({
        "task_contract": {"contract": task.contract, "entry_point": task.entry_point,
                          "editable_path": task.editable_path, "public_tests": task.public_tests},
        "base_repository": {path: sha256_bytes(body.encode("utf-8")) for path, body in task.base_files.items()},
        "replacement_file": sha256_bytes(replacement.encode("utf-8")),
        "environment_version": environment, "check_versions": check_versions,
        "allowed_source_manifest": task.source_manifest,
    }))


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def parse_json(text: str):
    def reject_constant(value):
        raise ValueError(f"non-finite JSON constant: {value}")
    value = json.loads(text, object_pairs_hook=_pairs, parse_constant=reject_constant)
    canonical_json(value)  # Also rejects finite-looking literals that overflow float.
    return value


def read_json(path: Path) -> object:
    return parse_json(Path(path).read_text(encoding="utf-8"))


def write_json_atomic(path: Path, value: object) -> None:
    path = Path(path)
    data = canonical_json(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def read_events(path: Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    data = path.read_bytes()
    if data and not data.endswith(b"\n"):
        raise ValueError("incomplete JSONL event; reconcile before appending")
    result, seen = [], {}
    for line in data.splitlines():
        event = parse_json(line.decode("utf-8"))
        if not isinstance(event, dict):
            raise ValueError("event must be an object")
        _text(event.get("event_id"), "event_id")
        if event["event_id"] in seen:
            raise ValueError("duplicate event ID in ledger")
        seen[event["event_id"]] = event
        result.append(event)
    return result


def append_event(path: Path, event: dict) -> bool:
    if not isinstance(event, Mapping):
        raise ValueError("event must be an object")
    _text(event.get("event_id"), "event_id")
    encoded = canonical_json(event)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        for existing in read_events(path):
            if existing["event_id"] == event["event_id"]:
                if canonical_json(existing) != encoded:
                    raise ValueError("conflicting duplicate event ID")
                return False
        stream.write(encoded + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    return True
