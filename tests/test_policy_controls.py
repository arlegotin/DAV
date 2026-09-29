import importlib

import numpy as np
import pytest

from depverify.records import CHECK_IDS, EMPTY_HISTORY, LINEAGES
from conftest import constant_joint, independent_joint, perfect_joint, uninformative_pair_joint, xor_joint
from test_policy import exhaustive_realized


def policies():
    return importlib.import_module("depverify.policy")


def test_useless_checks_are_not_bought_and_all_unknown_terminates():
    p = policies()
    joint = constant_joint()
    assert p.plan(joint, EMPTY_HISTORY, frozenset(CHECK_IDS), dict.fromkeys(CHECK_IDS, .1)) == ("DEFER", 5.)
    assert p.plan(joint, ("UNKNOWN",) * 4, frozenset(CHECK_IDS), dict.fromkeys(CHECK_IDS, .1)) == ("DEFER", 5.)


def test_free_perfect_and_expensive_perfect_and_missing_action():
    p, joint = policies(), perfect_joint()
    action, value = p.plan(joint, EMPTY_HISTORY, frozenset({"R1"}), {"R1": 0.})
    assert (action, value) == ("R1", 2.5)
    assert p.plan(joint, EMPTY_HISTORY, frozenset({"R1"}), {"R1": 3.}) == ("DEFER", 5.)
    assert p.plan(joint, EMPTY_HISTORY, frozenset(), {}) == ("DEFER", 5.)


def test_complementary_pair_with_no_singleton_information_is_bought():
    p, joint = policies(), xor_joint()
    assert joint[1].sum() == .5
    assert joint[1, 0].sum() / joint[:, 0].sum() == .5
    action, value = p.plan(joint, EMPTY_HISTORY, frozenset({"R1", "R2"}), {"R1": .1, "R2": .1})
    assert action == "R1"
    assert value == pytest.approx(2.7)


@pytest.mark.parametrize("cost,wanted_gain", [(.1, True), (3., False)])
def test_changed_coupling_preserves_marginals_and_sometimes_changes_economics(cost, wanted_gain):
    p, true, independent = policies(), xor_joint(), uninformative_pair_joint()
    for y in (0, 1):
        for check in (0, 1):
            axes = tuple(i for i in range(4) if i != check)
            np.testing.assert_array_equal(true[y].sum(axis=axes), independent[y].sum(axis=axes))
    costs, available = {"R1": cost, "R2": cost}, frozenset({"R1", "R2"})
    pair_policy = p.make_policy({g: true for g in LINEAGES}, costs)
    independent_policy = p.make_policy({g: independent for g in LINEAGES}, costs)
    pair_realized = exhaustive_realized(true, pair_policy, available, costs)
    independent_realized = exhaustive_realized(true, independent_policy, available, costs)
    if wanted_gain:
        assert pair_policy("same_lineage", available, EMPTY_HISTORY)[0] == "R1"
        assert independent_policy("same_lineage", available, EMPTY_HISTORY)[0] == "DEFER"
        assert pair_realized == pytest.approx(2.7)
        assert independent_realized == 5.
    else:
        assert pair_realized == independent_realized == 5.


def test_asymmetric_failure_rates_have_hand_calculated_expected_value():
    joint = np.zeros((2, 3, 3, 3, 3))
    joint[1, 0, 2, 2, 2], joint[1, 2, 2, 2, 2] = .4, .1
    joint[0, 0, 2, 2, 2], joint[0, 1, 2, 2, 2] = .05, .45
    action, value = policies().plan(joint, EMPTY_HISTORY, frozenset({"R1"}), {"R1": .1})
    assert action == "R1"
    assert value == pytest.approx(3.35)  # .1 work + .05*20 wrong accept + .45*5 defer


def test_dominant_cheap_test_does_not_manufacture_review_value():
    joint = np.zeros((2, 3, 3, 3, 3))
    joint[1, 2, 2, 0, 2], joint[0, 2, 2, 1, 2] = .5, .5
    costs = {"R1": .1, "R2": .1, "T": .01, "D": .1}
    action, value = policies().plan(joint, EMPTY_HISTORY, frozenset(CHECK_IDS), costs)
    assert action == "T"
    assert value == pytest.approx(2.51)


def test_informative_mixed_modalities_have_positive_bounded_acquisition_value():
    action, value = policies().plan(independent_joint(), EMPTY_HISTORY, frozenset(CHECK_IDS),
                                   {"R1": .2, "R2": .2, "T": .05, "D": .5})
    assert action in CHECK_IDS
    assert 0. < value < 5.
