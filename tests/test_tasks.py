from dataclasses import replace
import importlib

import pytest

from depverify.records import Proposal, Task, proposal_key, sha256_bytes

REPLACEMENT = "def solve(x):\n    return x\n"
ENVIRONMENT = {"version": "fake-v1"}
CHECK_VERSIONS = {"R1": "fake-v1", "R2": "fake-v1", "T": "fake-v1", "D": "fake-v1"}


def tasks():
    return importlib.import_module("depverify.tasks")


def proposal_and_identity(task, actor_metadata, replacement=REPLACEMENT):
    key = proposal_key(task, replacement, ENVIRONMENT, CHECK_VERSIONS)
    proposal = Proposal(task.episode_id, key, replacement, "ok", actor_metadata, 0.)
    return proposal, {"proposal_key": key, "environment": ENVIRONMENT, "check_versions": CHECK_VERSIONS}


def public_hashes(root, task):
    return {name: sha256_bytes((root / name).read_bytes()) for name in task.base_files}


def test_accept_and_defer_touch_only_their_disposable_copy(tmp_path, task_fields, actor_metadata):
    t = tasks()
    task = Task(**task_fields)
    original = t.materialize(task, tmp_path)
    accepted = t.materialize(task, tmp_path)
    deferred = t.materialize(task, tmp_path)
    original_hashes = public_hashes(original, task)
    proposal, identity = proposal_and_identity(task, actor_metadata)
    assert t.preflight(task, REPLACEMENT, accepted)[0] == "ok"
    result = t.apply_or_defer(task, proposal, "ACCEPT", accepted, identity)
    assert result["status"] == "applied"
    assert result["after_hashes"]["candidate.py"] == sha256_bytes(REPLACEMENT.encode())
    assert result["after_hashes"]["support.py"] == original_hashes["support.py"]
    deferred_result = t.apply_or_defer(task, proposal, "DEFER", deferred, identity)
    assert deferred_result["status"] == "deferred"
    assert public_hashes(original, task) == original_hashes
    assert public_hashes(deferred, task) == original_hashes


def test_repeated_acceptance_is_idempotent(tmp_path, task_fields, actor_metadata):
    t = tasks()
    task = Task(**task_fields)
    root = t.materialize(task, tmp_path)
    proposal, identity = proposal_and_identity(task, actor_metadata)
    t.apply_or_defer(task, proposal, "ACCEPT", root, identity)
    before = (root / "candidate.py").stat().st_mtime_ns
    result = t.apply_or_defer(task, proposal, "ACCEPT", root, identity)
    assert result["status"] == "already_applied"
    assert (root / "candidate.py").stat().st_mtime_ns == before


@pytest.mark.parametrize("body,status", [("def solve(:", "syntax_error"),
                                         ("def wrong(x): return x", "entry_point_error"),
                                         ("def solve(x,y): return x", "entry_point_error"),
                                         ("x = 0\n" + "#" * 65536, "size_limit")])
def test_mechanical_errors_defer_without_writing(tmp_path, task_fields, actor_metadata, body, status):
    t = tasks()
    task = Task(**task_fields)
    root = t.materialize(task, tmp_path)
    before = public_hashes(root, task)
    assert t.preflight(task, body, root)[0] == status
    proposal, identity = proposal_and_identity(task, actor_metadata, body)
    result = t.apply_or_defer(task, proposal, "ACCEPT", root, identity)
    assert result["status"] == status
    assert public_hashes(root, task) == before


def test_preflight_never_runs_python(tmp_path, task_fields):
    task = Task(**task_fields)
    root = tasks().materialize(task, tmp_path)
    source = 'raise RuntimeError("host execution")\ndef solve(x): return x\n'
    assert tasks().preflight(task, source, root)[0] == "ok"


@pytest.mark.parametrize("bad_path", ["../outside.py", "/tmp/outside.py", "a/../../outside.py"])
def test_materialization_rejects_escape_paths(tmp_path, task_fields, bad_path):
    task = Task(**(task_fields | {"editable_path": bad_path, "base_files": {bad_path: "def solve(x): return x"}}))
    with pytest.raises(ValueError):
        tasks().materialize(task, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_symlink_escape_and_changed_protected_files_refuse_apply(tmp_path, task_fields, actor_metadata):
    task = Task(**task_fields)
    t = tasks()
    root = t.materialize(task, tmp_path)
    outside = tmp_path / "outside.py"
    outside.write_text("canary")
    proposal, identity = proposal_and_identity(task, actor_metadata)
    (root / "candidate.py").unlink()
    (root / "candidate.py").symlink_to(outside)
    assert t.apply_or_defer(task, proposal, "ACCEPT", root, identity)["status"] == "invalid_path"
    assert outside.read_text() == "canary"
    second = t.materialize(task, tmp_path)
    assert t.preflight(task, REPLACEMENT, second)[0] == "ok"
    (second / "support.py").write_text("VERSION = 2")
    assert t.apply_or_defer(task, proposal, "ACCEPT", second, identity)["status"] == "stale_identity"
    assert (second / "candidate.py").read_text() == task.base_files["candidate.py"]


def test_nested_symlink_directory_and_unmarked_root_refuse_apply(tmp_path, task_fields, actor_metadata):
    task = Task(**(task_fields | {"editable_path": "pkg/candidate.py", "base_files": {"pkg/candidate.py": "def solve(x): return 0"}}))
    t = tasks()
    root = t.materialize(task, tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "candidate.py").write_text("canary")
    (root / "pkg/candidate.py").unlink()
    (root / "pkg").rmdir()
    (root / "pkg").symlink_to(outside, target_is_directory=True)
    proposal, identity = proposal_and_identity(task, actor_metadata)
    assert t.apply_or_defer(task, proposal, "ACCEPT", root, identity)["status"] == "invalid_path"
    assert (outside / "candidate.py").read_text() == "canary"
    assert t.apply_or_defer(task, proposal, "ACCEPT", outside, identity)["status"] == "invalid_root"


def test_extra_files_and_altered_editable_file_fail_preflight(tmp_path, task_fields):
    t = tasks()
    task = Task(**task_fields)
    root = t.materialize(task, tmp_path)
    (root / "extra.py").write_text("pass")
    assert t.preflight(task, REPLACEMENT, root)[0] == "out_of_scope"
    (root / "extra.py").unlink()
    (root / "candidate.py").write_text("tampered")
    assert t.preflight(task, REPLACEMENT, root)[0] == "stale_identity"


def test_nested_marker_name_is_not_an_allowlisted_file(tmp_path, task_fields):
    task = Task(**task_fields)
    root = tasks().materialize(task, tmp_path)
    (root / "extra").mkdir()
    (root / "extra/.depverify-task.json").write_text("{}")
    assert tasks().preflight(task, REPLACEMENT, root)[0] == "out_of_scope"


@pytest.mark.parametrize("changed", [{"environment": {"version": "other"}}, {"proposal_key": "0" * 64},
                                     {"check_versions": {"R1": "other"}}])
def test_stale_environment_or_proposal_cannot_apply(tmp_path, task_fields, actor_metadata, changed):
    t = tasks()
    task = Task(**task_fields)
    root = t.materialize(task, tmp_path)
    proposal, identity = proposal_and_identity(task, actor_metadata)
    result = t.apply_or_defer(task, proposal, "ACCEPT", root, identity | changed)
    assert result["status"] == "stale_identity"
    assert (root / "candidate.py").read_text() == task.base_files["candidate.py"]


def test_split_roots_cannot_overlap_and_episode_ids_are_unique(task_fields):
    t = tasks()
    train = Task(**(task_fields | {"split": "train"}))
    test = replace(train, episode_id="other", split="test")
    with pytest.raises(ValueError):
        t.validate_splits([train, test])
    with pytest.raises(ValueError):
        t.validate_splits([train, train])
    t.validate_splits([train, replace(train, episode_id="variant")])
