"""Inert fake runner. Real isolated execution is deliberately absent at M0."""

from collections.abc import Mapping, Sequence
import math

from .records import canonical_json, parse_json


class FakeRunner:
    def __init__(self, responses: Mapping[str, dict]):
        self._responses = parse_json(canonical_json(responses).decode("utf-8"))
        self._invocations = 0

    def run(self, proposal_key: str, inputs: Sequence[object]) -> dict:
        if proposal_key not in self._responses:
            raise ValueError("no registered fake response")
        response = parse_json(canonical_json(self._responses[proposal_key]).decode("utf-8"))
        if not isinstance(response, dict) or not {"status", "inputs", "outputs", "elapsed_seconds"}.issubset(response):
            raise ValueError("incomplete fake response")
        if canonical_json(response["inputs"]) != canonical_json(inputs):
            raise ValueError("fake response requires exact registered inputs")
        if not isinstance(response["outputs"], list) or len(response["outputs"]) != len(inputs):
            raise ValueError("fake response input/output count mismatch")
        elapsed = response["elapsed_seconds"]
        if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError("invalid fake execution cost")
        self._invocations += 1
        return response | {"fake": True, "invocation": self._invocations}
