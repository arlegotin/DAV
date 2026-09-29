"""Trusted masked replay; private scoring is performed after decisions."""

from collections.abc import Callable, Mapping
import time

from .records import CHECK_IDS, CheckResult, Decision, Proposal


def replay_episode(proposal: Proposal, lineage: str, available: frozenset[str], policy: Callable,
                   evidence: Mapping[str, CheckResult], *, policy_hash: str) -> Decision:
    started = time.perf_counter()
    history, acquired, selected_seconds = [None] * 4, [], 0.

    def finish(action, status):
        return Decision(proposal.proposal_key, policy_hash, tuple(acquired), action, status,
                        selected_seconds, time.perf_counter() - started, 0.)

    if proposal.status != "ok":
        return finish("DEFER", "invalid_proposal")
    if not isinstance(available, frozenset) or not available.issubset(CHECK_IDS):
        return finish("DEFER", "invalid_availability")

    def request(check_id: str) -> str:
        nonlocal selected_seconds
        if check_id not in available:
            raise ValueError("unavailable_request")
        index = CHECK_IDS.index(check_id)
        if history[index] is not None:
            raise ValueError("duplicate_request")
        try:
            result = evidence[check_id]
        except KeyError as exc:
            raise ValueError("missing_evidence") from exc
        if not isinstance(result, CheckResult):
            raise ValueError("invalid_evidence")
        if result.proposal_key != proposal.proposal_key or result.check_id != check_id:
            raise ValueError("stale_evidence")
        selected_seconds += result.elapsed_seconds
        acquired.append((check_id, result.verdict))
        history[index] = result.verdict
        return result.verdict

    for _ in range(5):
        if history[2] == "FAIL":
            return finish("DEFER", "public_fail_veto")
        try:
            choice = policy(lineage, available, tuple(history))
        except Exception:
            return finish("DEFER", "policy_error")
        if not isinstance(choice, tuple) or len(choice) != 2 or not all(isinstance(v, str) and v for v in choice):
            return finish("DEFER", "invalid_policy_output")
        action, status = choice
        if action == "DEFER":
            return finish(action, status)
        if status != "ok":
            return finish("DEFER", status)
        if action == "ACCEPT":
            return finish(action, status)
        if action not in CHECK_IDS:
            return finish("DEFER", "invalid_policy_output")
        try:
            request(action)
        except ValueError as exc:
            return finish("DEFER", str(exc))
    return finish("DEFER", "acquisition_limit")
