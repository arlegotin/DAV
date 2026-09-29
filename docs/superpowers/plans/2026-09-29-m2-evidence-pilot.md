# M2 evidence pilot implementation plan

> Use superpowers:executing-plans, current main, native execution and meaningful commits already authorized. Build only this milestone. M1 GO is recorded on the separately identified 1.5B fallback; later research gates stay unchanged.

**Goal:** Collect exactly 24 natural proposals and four fixed checks for each mechanically valid proposal, compare eight fixed eager-grounded tasks separately, then decide whether useful verification headroom exists.

**Architecture:** One collection module owns frozen inputs, serial native inference, immutable records/resume, a host-only labeler, and a budget/memory checkpoint. Policy.py receives only masked verdicts. One CPU pilot-analysis module evaluates fixed screening policies and root-level error overlap; no probability fitting/controller expansion before M2 GO. Labels remain a separate private file. Existing runtime adapters remain unchanged.

**Constraints:** All existing source/model/check caps, timeout reservations, no output repair or favorable retry, one model/request/container, hidden evaluator isolation, conservative roots, and original M2 gates apply. Keep six roots/four variants and the fixed failed proposals. M2 budget is 3,600 model-active seconds including startup/warmup/failures, within the unchanged 43,200-second total. Refuse infeasible work with a 1.5× forecast. No replacement pilot except the original bounded documented-defect rule; no manufactured natural failures.

**Review focus:** missing/stale prerequisites reject before calls; crash/resume never regenerates a completed bad proposal or double bills; check inputs don't see earlier outcomes; public failures and private labels cannot leak to model/controller; malformed proposals remain in denominators; eager proposals aren't paired verifier ablations; UNKNOWN and undefined efficiency never become success.

### Task 1: immutable serial collection and dry-run

Files: new collection.py and tests/test_collection.py; extend CLI only.

- [ ] Write missing-gate, immutable resume, natural denominator, fixed seeds/order, and eager-input-isolation regressions; observe RED.
- [ ] Implement M1 input-inventory validation, current M0 gate, fixed split/source/model/seed freeze, complete call recovery and original-cost charging, one serial warmup, preflight, independent check calls, host grading, and ledger-aware checkpoints.
- [ ] Use exactly one raw proposal per natural episode. Only mechanically valid proposals acquire R1/R2/T/D, in balanced fixed randomized order with fresh environments. Derive lineage from manifest identities/hashes. Persist Task/Proposal/CheckResult and separate labels. Complete records are immutable and resumed without regeneration.
- [ ] Choose eager task IDs from the smallest eight SHA256(task ID) values before outcomes; expose all allowed packets in that actor's prompt, then T, with its own proposal/label/cost records.
- [ ] `collect --split pilot --resume --dry-run` displays natural/eager counts, token ceiling including warmup, measured time/margin, remaining stage/total budget, and required GO; makes no model call. Later splits reject unimplemented/failed gates.
- [ ] Run full ordinary pytest; commit `feat: collect the bounded natural pilot with immutable resume`.

### Task 2: CPU headroom analysis and screening gate

Files: new pilot.py, tests/test_pilot.py, extend evaluate CLI.

- [ ] Write RED tests for unresolved labels, malformed natural denominators, public-failure contradiction, dominant-test/no-headroom stop, and complementary genuine errors across roots.
- [ ] Score always accept/defer, T-only, PASS-only single checks, fixed orders with early FAIL stopping, and all-checks diagnostics through masked replay. This is pilot screening, not final model tuning or confirmatory evidence.
- [ ] Report correct/incorrect/invalid counts, per-Y verdict/status rates, error sets and root support, original selected-action costs plus actor/preflight overhead, source-pair outcomes, and eager-system results separately. Optimistic fully observed diagnostics are labeled; no hidden evaluator is an acquisition action.
- [ ] Apply original M2 support/complementarity/T-pass-error/selection/headroom/leak/budget gates. One-class/difficulty scarcity is INCONCLUSIVE; dominance/no useful complementary checks is NO_GO; unresolved/environment/benchmark defects are BLOCKED. No thresholds or tasks change to rescue a result.
- [ ] Run full ordinary pytest; commit `feat: score pilot verification headroom without future-label access`.

### Task 3: run, audit, decide, and freeze the executed prefix

Files: reports/m2.md, final.md, frozen artifact manifest, README/current summary.

- [ ] Verify M0/current code and M1 relevant inventory; dry-run must fit before launching collection. Collect once with resume and all actual costs; stop/checkpoint on memory/budget problems or repeated timing slowdown.
- [ ] Evaluate; manually audit the first task ID in each root and every T/label contradiction by reading contract/code/deterministic counterexamples. No invented human review.
- [ ] Write the small JSON gate and report, all screening baselines, fixed trace examples, uncertainty limits, natural versus eager distinctions, and remaining unexecuted stages.
- [ ] If M2 isn't GO, finish the report and reproducibility checks; don't implement M3. If GO, only then write the M3 plan.
- [ ] Run ordinary checks and one fresh read-only review of this M2 range. Fix Important/Critical findings once via RED→GREEN, preserve minors/rulings, freeze current raw artifacts and meaningful commits.
