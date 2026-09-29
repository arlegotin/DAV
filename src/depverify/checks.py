"""Fixed check contracts and deterministic fake evidence, without inference."""

from collections.abc import Mapping

from .records import CHECK_IDS, VERDICTS, CheckResult, Proposal, canonical_json, parse_json, sha256_bytes


def parse_review(raw: str, *, truncated: bool = False) -> tuple[str, str, str]:
    if truncated:
        return "UNKNOWN", "truncated", ""
    if not isinstance(raw, str):
        return "UNKNOWN", "format_error", ""
    try:
        value = parse_json(raw)
        if not isinstance(value, dict) or set(value) != {"verdict", "reason"} or value["verdict"] not in VERDICTS or not isinstance(value["reason"], str):
            return "UNKNOWN", "format_error", ""
        return value["verdict"], "ok", value["reason"]
    except (ValueError, TypeError):
        refusal = raw.strip().lower().startswith(("i cannot", "i can't", "i refuse", "cannot review"))
        return "UNKNOWN", "refusal" if refusal else "format_error", ""


def fake_check(proposal: Proposal, check_id: str, fixture: dict) -> CheckResult:
    if check_id not in CHECK_IDS:
        raise ValueError("unknown check")
    metadata = dict(fixture["metadata"])
    raw = fixture.get("raw", "")
    supplied_status = fixture.get("status", "ok")
    if supplied_status == "ok" and metadata.get("timed_out") is True:
        supplied_status = "infrastructure_error" if check_id == "T" else "model_timeout"
    if supplied_status != "ok":
        verdict, reason, status = "UNKNOWN", "", supplied_status
        if check_id == "T" and supplied_status in ("candidate_failure", "candidate_timeout") and fixture.get("reproducible") is True:
            verdict, reason = "FAIL", "Reproducible violation of the fixed public invocation."
    elif check_id == "T":
        verdict = fixture.get("verdict", "UNKNOWN")
        reason, status = fixture.get("reason", "Fake public test result."), "ok"
    else:
        verdict, status, reason = parse_review(raw, truncated=fixture.get("truncated", False))
    metadata["raw_output_hash"] = sha256_bytes(raw.encode("utf-8") if raw else canonical_json({"verdict": verdict, "status": status}))
    metadata["fake"] = True
    return CheckResult(proposal.proposal_key, check_id, verdict, status, reason, fixture["elapsed_seconds"], metadata)


def check_cache_key(proposal: Proposal, check_id: str, prompt: bytes, settings: dict, sources: dict) -> str:
    required = {"check_version", "model_revision", "tokenizer_revision", "sampling_settings", "seed"}
    if check_id not in CHECK_IDS or not isinstance(prompt, bytes) or not isinstance(settings, Mapping) or not required.issubset(settings):
        raise ValueError("cache identity requires the full frozen check configuration")
    if type(settings["seed"]) is not int or settings["seed"] < 0:
        raise ValueError("cache seed must be a nonnegative integer")
    return sha256_bytes(canonical_json({"proposal_key": proposal.proposal_key, "check_id": check_id,
                                        "prompt_hash": sha256_bytes(prompt), "settings": settings, "sources": sources}))
