# SDD ledger — plan: docs/superpowers/plans/2026-10-03-audit-and-bounded-continuation.md

Base: 20ee603, user explicitly requested current branch and meaningful commits.
Pre-flight: Task 1 completion validation → Tasks 2/4 evaluation: shared validator must check exact bindings before reads.
Pre-flight: Task 3 prompt assembly → eager collection: eager inputs assembled explicitly, never decoded from presentation text.
Pre-flight: Task 3 runtime changes → Task 4 gates: refresh M0/M1 after all runtime edits; preserve original evidence in separate directories.
Ruling: continue inline on main without another approval round — explicit user authorization covers this audit, reversible repairs and the protocol’s single replacement pilot — cost if wrong: bounded local workload and reviewable commits.
Task 1: complete (commits 20ee603..42b0ff1, tests: .venv/bin/python -m pytest -q → 273 passed, 7 skipped in 4.71s)
Task 2: complete (commits 42b0ff1..29e538a, tests: .venv/bin/python -m pytest -q → 282 passed, 7 skipped in 4.71s)
Task 3: Ruling: remove Markdown delimiters from readable input presentation after fixed M1 smoke returned closing fences — a concrete wrapper defect before fresh pilot freezing; preserve outputs and all costs, rerun the same fixed inputs without stripping returned bytes — cost if wrong: one additional bounded M1 smoke and a reported setup failure, no further presentation changes.
Task 3: Ruling: scope fence removal to actor materials; restore the previously tested reviewer framing — the defect concerned actor output, and the broader change unnecessarily altered review inputs; all 12 restored prompts and model identities match the original raw records exactly, with both panels retained — cost if wrong: framing sensitivity may invalidate practical benefit, which must remain visible in the report.
Task 3: complete (commits 29e538a..989cb22, tests: .venv/bin/python -m pytest -q → 289 passed, 8 skipped in 5.63s)
Task 4: complete (commits 989cb22..8767587, tests: .venv/bin/python -m pytest -q → 291 passed, 8 skipped in 4.95s)
Final review: fresh-context independent internal review of 20ee603..8767587; one Important cleanup-before-smoke finding, no Critical or Minor findings. Full review retained in final-review.md.
Final: Ruling: current native model/isolation behavior was not rerun after NO_GO — historical evidence stays bound to its executed runtime; the final cleanup fix is verified with fake regressions and future experiments require fresh native prerequisites — cost if wrong: current native behavior may fail despite retained historical results, which cannot certify the changed runtime.
Final: Ruling: correctness beyond stored evaluator domains remains unestablished — labels mean passing the specified finite evaluator, and neither pilot is presented as universal correctness or deployment safety — cost if wrong: an accepted patch can fail on an unseen valid input.
Final: Ruling: development/download wall time and energy remain unmeasured — available model/container costs reconcile, while unavailable measurements are explicitly excluded from total-cost and energy claims — cost if wrong: omitted overhead can invalidate a practical break-even estimate, so no such estimate is claimed.
Final: fixed M1 model construction before cleanup validation — test_smoke_pending_execution_without_raw_record_blocks_model and test_smoke_retained_failed_cleanup_blocks_model, eight parameterized cases observed RED→GREEN; focused 35 passed, full suite 299 passed/8 skipped; commit a501d68.
Final verification: runs/m0/verification/6518728bc686452eb32a8e6e4371e7bc; pip check, fake doctor, 25 core controls, full pytest and git diff --check passed. No further model/container runs after NO_GO.
Deferred minors: none from the final review.
Finish: keep main and all research artifacts; user already chose current branch and meaningful commits. Preserve this owned workspace under runs/audit-2026-10-03/superpowers before deleting its scratch copy. No merge, push or publication.
