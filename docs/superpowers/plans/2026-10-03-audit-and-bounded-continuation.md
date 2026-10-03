# Audit and bounded continuation implementation plan

> Execute inline with Superpowers, on the current branch as explicitly requested.

Spec: `docs/superpowers/specs/2026-10-03-audit-and-bounded-continuation.md`.

## Global constraints

Preserve original frozen tasks and records. No new compute, changed economic weights, relaxed gate, second revision, favorable retries, or interruption of unrelated processes. Keep one model and one container at a time. Every expensive action needs current bound prerequisites and the existing ledger. User authorization already covers necessary reversible fixes and bounded continuation.

### Task 1: Fail closed on execution and resume defects

Interfaces: `ContainerRunner.run`, completion records, execution ledger, collection startup, M1 memory checks.

1. Add failing regression tests for engine loss after creation, pending execution reservation before model startup, and empty/incomplete/tampered completion records including all-complete resume. Run the focused tests; Expected: demonstrated failures.
2. Track whether creation may have happened, never certify cleanup after that merely because the engine vanished; retain staging and block. Validate exact completion bindings and all pending execution reservations before any early return or native load. Do not silently settle unknown execution.
3. Add a failing pre-load memory-guard test and make M1 apply the same resource guard used in collection. Expected: critical pressure prevents model load.
4. Run the focused and ordinary suites; Expected: pass, container tests remain opt-in. Commit the safety correction.

### Task 2: Correct estimands and screening

Interfaces: root-weighted summary, paired differences, pilot screen; consumes validated records from Task 1.

1. Add failing unequal-root rate and shuffled/missing/duplicate/mismatched paired-row tests. Derive literal expected values. Expected: current code fails these cases.
2. Compute rates with equal root weights, retain explicitly named raw rates. Join paired rows by identity and validate equal membership, proposal and root bindings.
3. Add a failing screen fixture where an indiscriminately rejecting reviewer appears complementary. Require useful correct-retaining checks and audited corrective evidence; keep raw catch counts as diagnostics. Enumerate all nonempty ordered check subsets for the prospective pilot, preserving the historical 32-policy table.
4. Implement and test the first-action economic bound using hand-derived examples. Produce an original-pilot diagnostic without rewriting its gate. Run suites and commit analysis corrections.

### Task 3: One readable task interface and admissible fresh benchmark

Interfaces: fixed prompt assembly, eager actor inputs, isolated response/host grading, task loader; consumes corrected guards and screening.

1. Specify one readable presentation, balanced review instructions, and fixed smoke fixture panel. Add behavior tests proving full multiline materials, no private data, unchanged cap/hash enforcement, and eager assembly without parsing prompt text. Expected: current wrapper fails the relevant new behavior tests.
2. Expose input mutation observations without sending private expectations to containers. Require only explicitly declared public immutability obligations. Align timeout grading with reproducible confirmation. Add real isolated fixtures and host grading tests.
3. Run ordinary checks, fresh M0 and isolated prerequisites, resource probes, and a freshly bound M1/revised public smoke. Expected: no leakage, reliable parsing, useful correct/incorrect fixture verdicts, measured budget feasible. Stop if this fails substantively.
4. If justified, build six fresh roots and four variants each; validate explicit domains, independent references, obligations and distinct mutants. Freeze revision identity and inputs before proposals; configure a separate revision directory and unchanged stage ledger. Run admission checks and commit the fixed interface and benchmark.

### Task 4: Execute the permitted revision and finish at its gate

Interfaces: separate frozen revision, original and revised artifacts, current M0/M1 authorizations, corrected screen and final reporting.

1. Dry-run the remaining 24 natural plus eight eager work with the existing ledger and 1.5x margin. Expected: feasible or checkpoint without launch.
2. Collect once, with balanced check order, complete records, resource monitoring and safe resume. Audit predetermined traces and every inconsistency. Evaluate with unchanged primary criteria; never promote an inconclusive result.
3. If M2 fails, finalize existing results, useful simpler workflow findings, claim A/B/C status, costs and reproducibility artifacts, explicitly leaving later milestones unexecuted. If it passes, write the next milestone-only plan and execute M3 under its unchanged gates.
4. Run appropriate final checks; commit the measured outcome. Obtain one fresh-context whole-change review; fix important findings once with RED→GREEN regressions and full suite. Preserve review/ledger in the audit record and finish without merging or publishing.

## Review focus

Check crash windows before raw execution records; unavailable engine after a container exists; complete records with omitted/hash-swapped/traversal paths; no model load before cleanup and resource checks; weighted denominators with unequal groups and unresolved cases; mismatched paired identities; screen false positives from unanimous rejection; hidden expected outputs and mutation requirements crossing the wrong boundary; fresh roots versus renamed old templates; one prospective prompt revision versus outcome-guided search; original freeze preservation; actual active-time accounting and no gate promotion.
