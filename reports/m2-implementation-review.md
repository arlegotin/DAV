# M2 implementation review

One fresh read-only reviewer checked `1b31128..0d3f3a1` and independently passed **262 tests, seven skipped**. It ran additional reproductions with fake inputs only. No download, native model or candidate container was launched. Verdict: three Important findings, no Critical or Minor findings. No second review was commissioned.

| Important finding | Fix and verification |
|---|---|
| Critical memory baseline did not stop loading | Baseline and post-load guards precede generation. RED→GREEN fake critical-pressure test proves zero loads/calls. An ongoing warning after the recorded pressure stop also prevents a restart. |
| Resume forgot unconfirmed container cleanup | Fresh, cached and recovered invocation results retain cleanup obligations. False cleanup blocks later model/candidate work, including when a saved T result would otherwise be skipped. RED→GREEN regression and retained-record case. |
| Unresolved eager labels could still permit GO | Eager evaluator resolution and an explicit completed eager comparison now participate in the M2 gate. Eight unresolved eager labels with otherwise positive synthetic natural screening now BLOCK; RED→GREEN. |

The single fix pass passes **267 ordinary tests, seven opt-in real-container tests skipped**. These are harness corrections; existing proposals, verdicts, labels, sources, seed schedule, penalties and memory thresholds were not rerun or changed.

The original collection freeze remains immutable. Resume after these guard corrections requires the exact [guard amendment](../runs/m2/resume-guard-amendment.json), binding the original freeze and reviewed execution hashes. A trusted AST comparison confirms unchanged actor messages, model request construction, source lineage, seed/order generation, public-test comparison, grading inputs and container invocation arguments. Changed task/model/source/sampling inputs are refused; this is not a gate override. New workers perform a separately billed actual warmup before timings.

Reviewer limitations and rulings:

- Native performance, isolation certification and pressure causality were outside this review. Existing M1 evidence covers this machine only; model-free warning pressure does not establish a cause. Replication can differ, and this is no hostile shared-hosting guarantee.
- Scientific headroom and mechanism efficacy remain unjudged because the prefix is incomplete and ineligible. A complete valid pilot is still required.
- M3–M5 and confirmatory statistics remain unexecuted. This report supports no efficiency/mechanism claim.
- Live wrapper latency was not measured. Replay discloses zero wrapper cost; live overhead could erase a later apparent saving.

Earlier deferred minors remain local to M0/M1: fake-flow policy names can collide, and smoke stores a preflight manifest under a misleading field name. M2 instead uses explicit frozen policy-definition hashes and numeric preflight latency. [Complete execution decisions](execution-decisions.md) retain rulings and their costs.

The review did not invalidate the current BLOCKED/INCONCLUSIVE evidence prefix. No additional model outcome was generated to verify these fixes.
