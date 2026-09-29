import importlib
import itertools

import numpy as np
import pytest

from depverify.records import CHECK_IDS, EMPTY_HISTORY, LINEAGES, VERDICTS, write_json_atomic
from conftest import constant_joint, copied_joint, independent_joint


def probability():
    return importlib.import_module("depverify.probability")


def direct_mass(joint, history, *, correct_only=False):
    total = 0.
    for y, outcomes in itertools.product(range(2), itertools.product(range(3), repeat=4)):
        if correct_only and y != 1:
            continue
        if all(value is None or VERDICTS[outcomes[j]] == value for j, value in enumerate(history)):
            total += joint[(y, *outcomes)]
    return total


def test_prior_and_copied_review_do_not_invent_information():
    p, joint = probability(), copied_joint()
    p.validate_joint(joint)
    assert p.posterior_correct(joint, EMPTY_HISTORY) == pytest.approx(.5)
    assert p.posterior_correct(joint, ("PASS", None, None, None)) == pytest.approx(.8)
    assert p.posterior_correct(joint, ("PASS", "PASS", None, None)) == pytest.approx(.8)
    assert p.predictive(joint, ("PASS", None, None, None), "R2").tolist() == [1., 0., 0.]


def test_exact_marginalization_and_total_probability_at_all_supported_histories():
    p, joint = probability(), independent_joint()
    p.validate_joint(joint)
    for history in itertools.product((None, *VERDICTS), repeat=4):
        expected = direct_mass(joint, history)
        assert p.history_mass(joint, history) == pytest.approx(expected, abs=1e-12)
        if expected == 0.:
            continue
        posterior = p.posterior_correct(joint, history)
        assert posterior == pytest.approx(direct_mass(joint, history, correct_only=True) / expected)
        for j, action in enumerate(CHECK_IDS):
            if history[j] is not None:
                continue
            predictions = p.predictive(joint, history, action)
            assert predictions.sum() == pytest.approx(1.)
            branches = 0.
            for verdict, mass in zip(VERDICTS, predictions):
                if mass == 0.:
                    continue
                new_history = list(history)
                new_history[j] = verdict
                branches += mass * p.posterior_correct(joint, tuple(new_history))
            assert branches == pytest.approx(posterior, abs=1e-12)


def test_unknown_is_observed_and_zero_support_is_explicit():
    p, joint = probability(), constant_joint(.9)
    assert p.history_mass(joint, (None, None, None, None)) == 1.
    assert p.posterior_correct(joint, ("UNKNOWN", None, None, None)) == pytest.approx(.9)
    with pytest.raises(p.ZeroSupportError):
        p.posterior_correct(joint, ("PASS", None, None, None))


@pytest.mark.parametrize("mutation", ["shape", "nan", "negative", "normalization", "public_contradiction", "object"])
def test_invalid_joint_tables_are_rejected(mutation):
    p, joint = probability(), constant_joint()
    if mutation == "shape":
        joint = joint[0]
    elif mutation == "nan":
        joint[0, 0, 0, 0, 0] = float("nan")
    elif mutation == "negative":
        joint[0, 0, 0, 0, 0] = -.1
    elif mutation == "normalization":
        joint *= .5
    elif mutation == "public_contradiction":
        joint[1, 2, 2, 2, 2] = 0.
        joint[1, 2, 2, 1, 2] = .5
    else:
        joint = joint.astype(object)
    with pytest.raises(ValueError):
        p.validate_joint(joint)


@pytest.mark.parametrize("history", [(None,), (None, None, None, "NOT_ACQUIRED"), (True, None, None, None)])
def test_invalid_history_is_rejected(history):
    with pytest.raises(ValueError):
        probability().history_mass(constant_joint(), history)


def test_predictive_rejects_repeated_or_unknown_check():
    p = probability()
    with pytest.raises(ValueError):
        p.predictive(constant_joint(), ("UNKNOWN", None, None, None), "R1")
    with pytest.raises(ValueError):
        p.predictive(constant_joint(), EMPTY_HISTORY, "HIDDEN")


@pytest.mark.parametrize("suffix", [".json", ".npz"])
def test_tables_round_trip_and_version_mismatch_defers_loading(tmp_path, suffix):
    p = probability()
    tables = {group: copied_joint() for group in LINEAGES}
    path = tmp_path / ("tables" + suffix)
    p.save_tables(path, tables, model_version="fake-v1")
    restored = p.load_tables(path, expected_version="fake-v1")
    assert set(restored) == set(LINEAGES)
    for group in LINEAGES:
        np.testing.assert_array_equal(restored[group], tables[group])
    with pytest.raises(ValueError):
        p.load_tables(path, expected_version="different")


def test_wrong_check_order_or_object_npz_cannot_load(tmp_path):
    p = probability()
    path = tmp_path / "wrong.json"
    write_json_atomic(path, {"schema_version": 1, "model_version": "fake-v1",
                             "check_ids": ["D", "T", "R1", "R2"], "verdicts": list(VERDICTS),
                             "tables": {g: constant_joint().tolist() for g in LINEAGES}})
    with pytest.raises(ValueError):
        p.load_tables(path, expected_version="fake-v1")
    path = tmp_path / "object.npz"
    np.savez(path, metadata=np.array({"schema_version": 1}, dtype=object))
    with pytest.raises(ValueError):
        p.load_tables(path, expected_version="fake-v1")
