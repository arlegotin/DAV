import pytest
import itertools
import numpy as np


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


def constant_joint(prior=.5):
    joint = np.zeros((2, 3, 3, 3, 3))
    joint[0, 2, 2, 2, 2] = 1 - prior
    joint[1, 2, 2, 2, 2] = prior
    return joint


def copied_joint():
    joint = np.zeros((2, 3, 3, 3, 3))
    joint[1, 0, 0, 2, 2] = .4
    joint[1, 1, 1, 2, 2] = .1
    joint[0, 0, 0, 2, 2] = .1
    joint[0, 1, 1, 2, 2] = .4
    return joint


def xor_joint():
    joint = np.zeros((2, 3, 3, 3, 3))
    for y, r1, r2 in [(1, 0, 0), (1, 1, 1), (0, 0, 1), (0, 1, 0)]:
        joint[y, r1, r2, 2, 2] = .25
    return joint


def uninformative_pair_joint():
    joint = np.zeros((2, 3, 3, 3, 3))
    for y, r1, r2 in itertools.product(range(2), repeat=3):
        joint[y, r1, r2, 2, 2] = .125
    return joint


def perfect_joint(check=0):
    joint = np.zeros((2, 3, 3, 3, 3))
    wrong, correct = [2, 2, 2, 2], [2, 2, 2, 2]
    wrong[check], correct[check] = 1, 0
    joint[(0, *wrong)] = .5
    joint[(1, *correct)] = .5
    return joint


def independent_joint():
    joint = np.zeros((2, 3, 3, 3, 3))
    for y, outcomes in itertools.product(range(2), itertools.product(range(3), repeat=4)):
        singles = ((.8, .1, .1), (.7, .2, .1), (1., 0., 0.), (.9, .05, .05)) if y else (
            (.2, .7, .1), (.3, .6, .1), (.2, .7, .1), (.1, .8, .1))
        joint[(y, *outcomes)] = .5 * np.prod([singles[j][o] for j, o in enumerate(outcomes)])
    return joint
