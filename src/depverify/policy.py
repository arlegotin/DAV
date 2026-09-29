"""Pure finite-horizon decisions over acquired verdicts only; no file access."""

from collections.abc import Callable, Mapping
from functools import lru_cache
import math

import numpy as np

from .probability import ZeroSupportError, history_mass, posterior_correct, predictive, validate_history, validate_joint
from .records import CHECK_IDS, LINEAGES, VERDICTS, History

_TOL = 1e-12


def _finite_cost(value) -> bool:
    return not isinstance(value, bool) and isinstance(value, (float, int)) and math.isfinite(value) and value >= 0.


def _costs(costs: Mapping[str, float], wrong_accept: float, defer: float) -> dict[str, float]:
    if not isinstance(costs, Mapping) or any(c not in CHECK_IDS for c in costs):
        raise ValueError("costs must map known checks")
    if any(not _finite_cost(value) for value in costs.values()) or not _finite_cost(wrong_accept) or not _finite_cost(defer):
        raise ValueError("costs must be finite and nonnegative")
    return {check: float(cost) for check, cost in costs.items()}


def _availability(available: frozenset[str], costs: Mapping[str, float]) -> None:
    if not isinstance(available, frozenset) or not available.issubset(CHECK_IDS) or not available.issubset(costs):
        raise ValueError("availability requires known checks with declared costs")


def _solver(joint, costs, wrong_accept, defer):
    validate_joint(joint)
    table = joint.copy()
    table.setflags(write=False)

    @lru_cache(maxsize=None)
    def solve(history, available):
        if history[2] == "FAIL":
            return "DEFER", float(defer)
        try:
            p = min(1., max(0., posterior_correct(table, history)))
        except ZeroSupportError:
            return "DEFER", float(defer)
        accept_cost = wrong_accept * (1. - p)
        best_action, best_value = ("ACCEPT", accept_cost) if accept_cost < defer - _TOL else ("DEFER", float(defer))
        candidates = sorted((c for c in available if history[CHECK_IDS.index(c)] is None),
                            key=lambda c: (costs[c], CHECK_IDS.index(c)))
        for action in candidates:
            value = costs[action]
            for verdict, probability in zip(VERDICTS, predictive(table, history, action)):
                if probability == 0.:
                    continue
                branch = list(history)
                branch[CHECK_IDS.index(action)] = verdict
                value += float(probability) * solve(tuple(branch), available)[1]
            # Strict improvement preserves stopping ties and sorted action ties.
            if value < best_value - _TOL:
                best_action, best_value = action, value
        return best_action, float(best_value)

    return solve


def plan(joint: np.ndarray, history: History, available: frozenset[str], costs: Mapping[str, float],
         *, wrong_accept: float = 20., defer: float = 5.) -> tuple[str, float]:
    prices = _costs(costs, wrong_accept, defer)
    validate_history(history)
    _availability(available, prices)
    return _solver(joint, prices, wrong_accept, defer)(history, available)


def make_policy(tables: Mapping[str, np.ndarray], costs: Mapping[str, float], *, wrong_accept: float = 20.,
                defer: float = 5.) -> Callable[[str, frozenset[str], History], tuple[str, str]]:
    try:
        if not isinstance(tables, Mapping) or set(tables) != set(LINEAGES):
            raise ValueError("missing lineage calibration")
        prices = _costs(costs, wrong_accept, defer)
        frozen_tables = {g: np.array(t, copy=True) for g, t in tables.items()}
        solvers = {g: _solver(t, prices, wrong_accept, defer) for g, t in frozen_tables.items()}
    except (ValueError, TypeError):
        return lambda lineage, available, history: ("DEFER", "calibration_invalid")

    def choose(lineage, available, history):
        group = lineage if isinstance(lineage, str) and lineage in LINEAGES else "unknown_lineage"
        try:
            validate_history(history)
            _availability(available, prices)
            if history[2] == "FAIL":
                return "DEFER", "ok"
            if history_mass(frozen_tables[group], history) == 0.:
                return "DEFER", "zero_support"
            return solvers[group](history, available)[0], "ok"
        except (ValueError, TypeError):
            return "DEFER", "calibration_invalid"

    return choose


def always_accept(lineage: str, available: frozenset[str], history: History) -> tuple[str, str]:
    return "ACCEPT", "ok"


def always_defer(lineage: str, available: frozenset[str], history: History) -> tuple[str, str]:
    return "DEFER", "ok"


def test_only(lineage: str, available: frozenset[str], history: History) -> tuple[str, str]:
    validate_history(history)
    if history[2] is None:
        return ("T", "ok") if "T" in available else ("DEFER", "unavailable")
    return ("ACCEPT", "ok") if history[2] == "PASS" else ("DEFER", "ok")
