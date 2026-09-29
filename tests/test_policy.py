import importlib
import itertools
import math

import numpy as np
import pytest

from depverify.records import CHECK_IDS, EMPTY_HISTORY, LINEAGES, VERDICTS
from conftest import constant_joint, copied_joint, independent_joint, perfect_joint, xor_joint


def policies():
    return importlib.import_module("depverify.policy")


def exhaustive_realized(joint, policy, available, costs):
    total = 0.
    for y, vector in itertools.product(range(2), itertools.product(range(3), repeat=4)):
        mass = joint[(y, *vector)]
        if mass == 0.:
            continue
        history, charged, used = [None] * 4, 0., set()
        for _ in range(5):
            action, status = policy("same_lineage", available, tuple(history))
            assert status == "ok"
            if action in ("ACCEPT", "DEFER"):
                charged += 20. * (action == "ACCEPT" and y == 0) + 5. * (action == "DEFER")
                break
            assert action in available and action not in used
            used.add(action)
            charged += costs[action]
            index = CHECK_IDS.index(action)
            history[index] = VERDICTS[vector[index]]
        else:
            pytest.fail("policy did not terminate")
        total += mass * charged
    return total


@pytest.mark.parametrize("builder", [constant_joint, copied_joint, independent_joint, perfect_joint, xor_joint])
@pytest.mark.parametrize("costs", [dict.fromkeys(CHECK_IDS, 0.), {"R1": .1, "R2": .2, "T": .05, "D": .3}, dict.fromkeys(CHECK_IDS, 30.)])
def test_dp_value_equals_independently_enumerated_realized_cost(builder, costs):
    p, joint = policies(), builder()
    policy = p.make_policy({g: joint for g in LINEAGES}, costs)
    for mask in range(16):
        available = frozenset(c for i, c in enumerate(CHECK_IDS) if mask & (1 << i))
        _, expected = p.plan(joint, EMPTY_HISTORY, available, costs)
        realized = exhaustive_realized(joint, policy, available, costs)
        assert expected == pytest.approx(realized, abs=1e-12)


def test_every_history_and_mask_has_finite_value_and_bounded_trajectory():
    p, joint, costs = policies(), independent_joint(), dict.fromkeys(CHECK_IDS, .1)
    policy = p.make_policy({g: joint for g in LINEAGES}, costs)
    for history in itertools.product((None, *VERDICTS), repeat=4):
        for mask in range(16):
            available = frozenset(c for i, c in enumerate(CHECK_IDS) if mask & (1 << i))
            action, value = p.plan(joint, history, available, costs)
            assert math.isfinite(value)
            assert action in ("ACCEPT", "DEFER", *available)
            observed = list(history)
            used = {CHECK_IDS[i] for i, verdict in enumerate(history) if verdict is not None}
            for _ in range(5):
                action, status = policy("same_lineage", available, tuple(observed))
                if action in ("ACCEPT", "DEFER"):
                    break
                assert action not in used
                used.add(action)
                observed[CHECK_IDS.index(action)] = "UNKNOWN"
            else:
                pytest.fail("policy exceeded four acquisitions")


def test_copied_observation_is_not_purchased_after_original():
    action, value = policies().plan(copied_joint(), ("PASS", None, None, None), frozenset({"R2"}), {"R2": 0.})
    assert action == "ACCEPT"
    assert value == pytest.approx(4.)


def test_terminal_ties_prefer_deferral_and_zero_cost_redundant_check_is_skipped():
    p = policies()
    assert p.plan(constant_joint(.75), EMPTY_HISTORY, frozenset(), {}) == ("DEFER", 5.)
    assert p.plan(constant_joint(.75), EMPTY_HISTORY, frozenset({"R1"}), {"R1": 0.}) == ("DEFER", 5.)


def test_equal_informative_action_ties_use_cost_then_fixed_id():
    joint = np.zeros((2, 3, 3, 3, 3))
    joint[1, 0, 0, 2, 2], joint[0, 1, 1, 2, 2] = .5, .5
    p = policies()
    assert p.plan(joint, EMPTY_HISTORY, frozenset({"R1", "R2"}), {"R1": .1, "R2": .1})[0] == "R1"
    assert p.plan(joint, EMPTY_HISTORY, frozenset({"R1", "R2"}), {"R1": .2, "R2": .1})[0] == "R2"


@pytest.mark.parametrize("cost", [-1., float("nan"), float("inf"), True])
def test_invalid_costs_defer_at_policy_boundary(cost):
    p = policies()
    policy = p.make_policy({g: constant_joint() for g in LINEAGES}, {"R1": cost})
    assert policy("same_lineage", frozenset({"R1"}), EMPTY_HISTORY) == ("DEFER", "calibration_invalid")
    with pytest.raises(ValueError):
        p.plan(constant_joint(), EMPTY_HISTORY, frozenset({"R1"}), {"R1": cost})


def test_missing_corrupt_or_changed_calibration_cannot_accept():
    p = policies()
    for tables in ({}, {g: np.zeros((2, 3, 3, 3, 3)) for g in LINEAGES}):
        policy = p.make_policy(tables, {})
        assert policy("same_lineage", frozenset(), EMPTY_HISTORY) == ("DEFER", "calibration_invalid")
    tables = {g: constant_joint(.9) for g in LINEAGES}
    costs = {"R1": .1}
    policy = p.make_policy(tables, costs)
    tables["same_lineage"][:] = 0.
    costs["R1"] = float("nan")
    assert policy("same_lineage", frozenset(), EMPTY_HISTORY) == ("ACCEPT", "ok")


def test_unknown_lineage_uses_unknown_table_and_zero_support_defers():
    p = policies()
    tables = {g: constant_joint(.9) for g in LINEAGES}
    tables["unknown_lineage"] = constant_joint(.5)
    policy = p.make_policy(tables, {"R1": 0.})
    assert policy("unseen-name", frozenset(), EMPTY_HISTORY) == ("DEFER", "ok")
    assert policy("same_lineage", frozenset(), ("PASS", None, None, None)) == ("DEFER", "zero_support")


def test_fixed_policies_use_only_observed_public_tests():
    p = policies()
    available = frozenset(CHECK_IDS)
    assert p.always_accept("same_lineage", available, EMPTY_HISTORY) == ("ACCEPT", "ok")
    assert p.always_defer("same_lineage", available, EMPTY_HISTORY) == ("DEFER", "ok")
    assert p.test_only("same_lineage", available, EMPTY_HISTORY) == ("T", "ok")
    for verdict, action in [("PASS", "ACCEPT"), ("FAIL", "DEFER"), ("UNKNOWN", "DEFER")]:
        assert p.test_only("same_lineage", available, (None, None, verdict, None))[0] == action
    assert p.test_only("same_lineage", frozenset(), EMPTY_HISTORY)[0] == "DEFER"


def test_acquired_public_failure_is_a_hard_veto_even_on_impossible_history():
    p = policies()
    assert p.plan(constant_joint(.99), (None, None, "FAIL", None), frozenset(), {}) == ("DEFER", 5.)
    policy = p.make_policy({g: constant_joint(.99) for g in LINEAGES}, {})
    assert policy("same_lineage", frozenset(), (None, None, "FAIL", None))[0] == "DEFER"
