import importlib

import pytest

from depverify.records import Proposal


def checks():
    return importlib.import_module("depverify.checks")


@pytest.mark.parametrize("raw", ["PASS", 'prefix {"verdict":"PASS","reason":"x"}',
                                '{"verdict":"PASS","reason":"x","extra":1}',
                                '{"verdict":"FAIL","verdict":"PASS","reason":"x"}',
                                '{"verdict":"PASS","reason":1}', '{"verdict":"pass","reason":"x"}',
                                '{"verdict":"PASS","reason":NaN}', '["PASS"]', "I cannot review this."])
def test_malformed_or_refused_output_never_becomes_pass(raw):
    verdict, status, _ = checks().parse_review(raw)
    assert verdict == "UNKNOWN"
    assert status in ("format_error", "refusal")


def test_exact_review_contract_and_truncation():
    c = checks()
    raw = '{"verdict":"PASS","reason":"Matches."}'
    assert c.parse_review(raw) == ("PASS", "ok", "Matches.")
    assert c.parse_review(raw, truncated=True) == ("UNKNOWN", "truncated", "")
    assert c.parse_review('{"verdict":"UNKNOWN","reason":"Evidence unavailable."}') == (
        "UNKNOWN", "ok", "Evidence unavailable.")


def test_fake_reviews_keep_cost_and_distinct_action_ids(actor_metadata, check_metadata, monkeypatch):
    c = checks()
    def forbidden(*args, **kwargs):
        raise AssertionError("fake checks must not sleep or infer")
    monkeypatch.setattr("time.sleep", forbidden)
    proposal = Proposal("fake-001", "1" * 64, "pass", "ok", actor_metadata, 0.)
    fixture = {"raw": '{"verdict":"PASS","reason":"same bytes"}', "elapsed_seconds": 12.,
               "metadata": check_metadata}
    first = c.fake_check(proposal, "R1", fixture)
    second = c.fake_check(proposal, "R2", fixture)
    assert first.verdict == second.verdict == "PASS"
    assert first.check_id == "R1" and second.check_id == "R2"
    assert first.elapsed_seconds == second.elapsed_seconds == 12.
    assert first.metadata["raw_output_hash"] == second.metadata["raw_output_hash"]


@pytest.mark.parametrize("status,reproducible,verdict", [("candidate_failure", True, "FAIL"),
                                                        ("candidate_timeout", True, "FAIL"),
                                                        ("candidate_failure", False, "UNKNOWN"),
                                                        ("infrastructure_error", False, "UNKNOWN"),
                                                        ("output_limit", False, "UNKNOWN")])
def test_public_candidate_failure_and_engine_failure_are_distinct(actor_metadata, check_metadata, status, reproducible, verdict):
    proposal = Proposal("fake-001", "1" * 64, "pass", "ok", actor_metadata, 0.)
    result = checks().fake_check(proposal, "T", {"status": status, "reproducible": reproducible,
                                                 "elapsed_seconds": 10., "metadata": check_metadata})
    assert result.verdict == verdict
    assert result.elapsed_seconds == 10.


@pytest.mark.parametrize("changed", ["seed", "model_revision", "tokenizer_revision", "sampling_settings", "check_version", "prompt", "source"])
def test_cache_identity_changes_for_every_relevant_input(actor_metadata, changed):
    c = checks()
    proposal = Proposal("fake-001", "1" * 64, "pass", "ok", actor_metadata, 0.)
    settings = {"seed": 1, "model_revision": "fake-v1", "tokenizer_revision": "fake-v1",
                "sampling_settings": {"temperature": 0}, "check_version": "review-v1"}
    prompt, sources = b"exact prompt", {"A": {"hash": "a" * 64, "version": "1"}}
    before = c.check_cache_key(proposal, "R1", prompt, settings, sources)
    settings = dict(settings)
    if changed in ("seed", "model_revision", "tokenizer_revision", "check_version"):
        settings[changed] = 2 if changed == "seed" else "changed"
    elif changed == "sampling_settings":
        settings[changed] = {"temperature": .2}
    elif changed == "prompt":
        prompt += b" "
    else:
        sources = {"A": {"hash": "b" * 64, "version": "1"}}
    assert c.check_cache_key(proposal, "R1", prompt, settings, sources) != before
    assert c.check_cache_key(proposal, "R2", prompt, settings, sources) != before


def test_incomplete_cache_settings_are_refused(actor_metadata):
    proposal = Proposal("fake-001", "1" * 64, "pass", "ok", actor_metadata, 0.)
    with pytest.raises(ValueError):
        checks().check_cache_key(proposal, "R1", b"x", {"seed": 1}, {})


def test_timed_out_review_cannot_supply_apparent_pass(actor_metadata, check_metadata):
    proposal = Proposal("fake-001", "1" * 64, "pass", "ok", actor_metadata, 0.)
    result = checks().fake_check(proposal, "R1", {"raw": '{"verdict":"PASS","reason":"x"}',
                                                  "metadata": check_metadata | {"timed_out": True},
                                                  "elapsed_seconds": 180.})
    assert (result.verdict, result.status) == ("UNKNOWN", "model_timeout")
    assert result.elapsed_seconds == 180.
