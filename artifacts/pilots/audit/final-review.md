# Final independent internal review

Reviewer: `/root/audit_final_review`; read-only, fresh context. Range: `20ee603..8767587`.
No model, Docker, candidate execution, files written, or process interruption by the reviewer.

One Important finding; no Critical or Minor findings.

M1 `_smoke_local` constructs `LocalModel` and reaches `model.start()` without checking pending execution reservations or retained cleanup failures. The collection cleanup guard is not invoked. A crash after container creation, before recording/settlement, can leave a container unaccounted for when smoke restarts.

CPU-only reproduction patched `pipeline.read_events` with a valid unsettled M1 execution reservation, mocked valid prerequisites/resource probes, disabled writes, and replaced the model with a start sentinel. `resume_attempts` reported pending work, but `_smoke_local` reached the sentinel. Required fix: validate cleanup/accounting before loading, including pending reservations without raw records and retained failed-cleanup records. No pilot rerun is needed.

The reviewer also confirmed:

- All 64 completed bundles validate, with exact proposal/check/evidence/label bindings and gate hashes.
- All 132 tracked and 3,890 raw pre-review manifest files match hashes.
- All 68 replacement summaries reproduce from saved scores.
- Paired bootstrap is invariant to ordering; missing/duplicate/mismatched identities are rejected; the reported T-versus-defer result reproduces.
- Costs reconcile to 370.832571 model seconds and 504.759299 container seconds.
- Restored diagnostic prompts and model identity validate; both framing panels are disclosed.
- Fresh roots are different algorithms. Host-side private outputs, mutation obligations, useful screening, separate eager proposals, and NO_GO interpretation are consistent.
- Historical native authorization is distinguished from modified runtime; the original INCONCLUSIVE is preserved and later stages remain unexecuted.

Declined to judge:

1. Current native model/isolation behavior: prohibited during review; retained evidence and code were inspected.
2. Exhaustive correctness beyond stored evaluator domains: finite-domain evidence cannot establish universal correctness; no candidate/reference execution in review.
3. Unmetered development/download wall time and energy: measurements unavailable and reported as such.

Author assessment: Important stands by its safety effect. Fix once with failing regressions and a passing full suite; no second review or expensive rerun.
