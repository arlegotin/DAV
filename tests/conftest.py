import pytest


@pytest.fixture
def task_fields():
    return {
        "episode_id": "fake-001", "root_group_id": "fake-root", "split": "fake",
        "task_class": "fake", "contract": "Return the input JSON value.",
        "editable_path": "candidate.py", "entry_point": "solve",
        "base_files": {"candidate.py": "def solve(x):\n    return None\n",
                       "support.py": "VERSION = 1\n"},
        "public_tests": ({"input": 2, "expected": 2},),
        "source_manifest": {"A": {"lineage_id": "manual-v1", "version": "1", "body": "Return x."}},
    }


@pytest.fixture
def actor_metadata():
    return {
        "model_revision": "fake", "tokenizer_revision": "fake", "seed": 1,
        "prompt_hash": "a" * 64, "environment_hash": "b" * 64,
        "input_tokens": 10, "output_tokens": 8, "elapsed_seconds": 8.0,
        "timed_out": False, "cache_hit": False,
        "sampling_settings": {"temperature": .2}, "attempt_id": "fake-actor-1",
    }


@pytest.fixture
def check_metadata():
    return {
        "check_version": "fake-v1", "model_revision": "fake", "tokenizer_revision": "fake",
        "check_seed": 2, "prompt_hash": "c" * 64, "source_hashes": {},
        "source_versions": {}, "input_tokens": 10, "output_tokens": 5,
        "timed_out": False, "cache_hit": False, "machine_profile_hash": "d" * 64,
        "environment_hash": "b" * 64, "attempt_ids": ["fake-review-1"],
    }
