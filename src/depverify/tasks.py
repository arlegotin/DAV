"""Public task checks and mutations restricted to marked disposable copies."""

import ast
from collections.abc import Sequence
import os
from pathlib import Path, PurePosixPath
import tempfile
import time

from .records import Proposal, Task, canonical_json, proposal_key, read_json, sha256_bytes, to_dict, write_json_atomic

_MARKER = ".depverify-task.json"
_REPLACEMENT_BYTES = 64 * 1024


def load_pilot() -> list[Task]:
    from .records import from_dict, parse_json
    public = Path(__file__).resolve().parents[2] / "bench/public"
    manifest = read_json(public / "pilot-manifest.json")
    data = (public / "pilot.jsonl").read_bytes()
    if sha256_bytes(data) != manifest["task_sha256"]:
        raise ValueError("pilot task manifest changed")
    tasks = [from_dict(Task, parse_json(line.decode())) for line in data.splitlines()]
    validate_splits(tasks)
    if len(tasks) != 24 or any(task.split != "pilot" for task in tasks):
        raise ValueError("pilot is exactly 24 episodes")
    return tasks


class _Rejected(ValueError):
    pass


def _relative(name: str) -> PurePosixPath:
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise _Rejected("invalid_path")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in name.split("/")) or name == _MARKER:
        raise _Rejected("invalid_path")
    return path


def _safe_file(root: Path, name: str) -> Path:
    relative = _relative(name)
    current = root
    for component in relative.parts:
        current = current / component
        if current.is_symlink():
            raise _Rejected("invalid_path")
    if not current.resolve().is_relative_to(root.resolve()):
        raise _Rejected("invalid_path")
    return current


def _task_hash(task: Task) -> str:
    return sha256_bytes(canonical_json(to_dict(task)))


def _root_identity(root: Path) -> dict:
    absolute = root.absolute()
    if any(path.is_symlink() for path in (absolute, *absolute.parents)):
        raise _Rejected("invalid_root")
    stat = absolute.stat()
    return {"path": str(absolute), "device": stat.st_dev, "inode": stat.st_ino}


def validate_splits(tasks: Sequence[Task]) -> None:
    seen_ids, root_splits = set(), {}
    for task in tasks:
        if task.episode_id in seen_ids:
            raise ValueError("duplicate episode ID")
        seen_ids.add(task.episode_id)
        if task.root_group_id in root_splits and root_splits[task.root_group_id] != task.split:
            raise ValueError("root group overlaps splits")
        root_splits[task.root_group_id] = task.split


def materialize(task: Task, parent: Path) -> Path:
    for name in task.base_files:
        _relative(name)  # Validate before creating any files.
    parent = Path(parent).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix=".depverify-", dir=parent))
    for name, body in task.base_files.items():
        path = _safe_file(root, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body.encode("utf-8"))
    write_json_atomic(root / _MARKER, {"schema_version": 1, "task_hash": _task_hash(task),
                                     "root_identity": _root_identity(root)})
    return root


def _snapshot(task: Task, root: Path) -> dict[str, str]:
    identity = _root_identity(root)
    if root.is_symlink() or not root.is_dir() or not root.name.startswith(".depverify-"):
        raise _Rejected("invalid_root")
    marker = root / _MARKER
    if marker.is_symlink() or not marker.is_file():
        raise _Rejected("invalid_root")
    try:
        if read_json(marker) != {"schema_version": 1, "task_hash": _task_hash(task), "root_identity": identity}:
            raise _Rejected("stale_identity")
    except (OSError, ValueError) as exc:
        if isinstance(exc, _Rejected):
            raise
        raise _Rejected("invalid_root") from exc
    names = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise _Rejected("invalid_path")
        if path.is_file() and path != marker:
            names.add(path.relative_to(root).as_posix())
    if names != set(task.base_files):
        raise _Rejected("out_of_scope")
    return {name: sha256_bytes(_safe_file(root, name).read_bytes()) for name in task.base_files}


def _validate(task: Task, replacement: str, root: Path, *, allow_applied=False) -> dict:
    if not isinstance(replacement, str):
        raise _Rejected("syntax_error")
    try:
        encoded = replacement.encode("utf-8")
    except UnicodeError as exc:
        raise _Rejected("syntax_error") from exc
    if len(encoded) > _REPLACEMENT_BYTES:
        raise _Rejected("size_limit")
    hashes = _snapshot(task, root)
    base_hashes = {name: sha256_bytes(body.encode("utf-8")) for name, body in task.base_files.items()}
    for name, digest in hashes.items():
        permitted = {base_hashes[name]}
        if allow_applied and name == task.editable_path:
            permitted.add(sha256_bytes(encoded))
        if digest not in permitted:
            raise _Rejected("stale_identity")
    try:
        tree = ast.parse(replacement)
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise _Rejected("syntax_error") from exc
    entries = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == task.entry_point]
    if len(entries) != 1:
        raise _Rejected("entry_point_error")
    args = entries[0].args
    required = len(args.posonlyargs) + len(args.args) - len(args.defaults)
    if required != 1 or any(default is None for default in args.kw_defaults):
        raise _Rejected("entry_point_error")
    return {"file_hashes": hashes,
            "protected_hashes": {name: digest for name, digest in hashes.items() if name != task.editable_path}}


def preflight(task: Task, replacement: str, candidate_root: Path) -> tuple[str, dict]:
    started = time.perf_counter()
    try:
        manifest = _validate(task, replacement, Path(candidate_root))
        status = "ok"
    except (_Rejected, OSError) as exc:
        status = str(exc) if isinstance(exc, _Rejected) else "infrastructure_error"
        manifest = {}
    manifest["elapsed_seconds"] = time.perf_counter() - started
    return status, manifest


def apply_or_defer(task: Task, proposal: Proposal, action: str, candidate_root: Path, expected_identity: dict) -> dict:
    started = time.perf_counter()
    if action not in ("ACCEPT", "DEFER"):
        raise ValueError("invalid terminal action")
    root, before, after = Path(candidate_root), {}, {}
    try:
        before = _snapshot(task, root)
        after = dict(before)
        if action == "DEFER":
            status = "deferred"
        elif proposal.status != "ok":
            status = "invalid_proposal"
        else:
            try:
                computed = proposal_key(task, proposal.replacement, expected_identity["environment"],
                                        expected_identity["check_versions"])
            except (KeyError, ValueError) as exc:
                raise _Rejected("stale_identity") from exc
            if proposal.episode_id != task.episode_id or computed != proposal.proposal_key or expected_identity.get("proposal_key") != computed:
                raise _Rejected("stale_identity")
            _validate(task, proposal.replacement, root, allow_applied=True)
            replacement_hash = sha256_bytes(proposal.replacement.encode("utf-8"))
            if before[task.editable_path] == replacement_hash:
                status = "already_applied"
            else:
                path = _safe_file(root, task.editable_path)
                # Recheck protected files just before the single atomic mutation.
                _validate(task, proposal.replacement, root, allow_applied=True)
                temporary = None
                try:
                    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                        temporary = Path(stream.name)
                        stream.write(proposal.replacement.encode("utf-8"))
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temporary, path)
                finally:
                    if temporary is not None:
                        temporary.unlink(missing_ok=True)
                status = "applied"
            after = _snapshot(task, root)
    except (_Rejected, OSError) as exc:
        status = str(exc) if isinstance(exc, _Rejected) else "infrastructure_error"
    return {"status": status, "wrapper_seconds": time.perf_counter() - started,
            "before_hashes": before, "after_hashes": after}
