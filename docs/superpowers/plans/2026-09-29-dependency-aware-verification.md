# Dependency-aware verification implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This document authorizes no execution by itself; the current request is to write the spec and plan.

**Goal:** Implement and verify M0 without a model, then advance through the conditional research roadmap only when the preceding gate passes.

**Architecture:** A small serial Python package holds validated records and known joint distributions. A pure exact planner sees only acquired verdicts, while trusted orchestration owns evidence, costs, labels, budgets, and disposable file changes. Real inference, container execution, fitting, and benchmark growth arrive only at their owning milestone.

**Tech Stack:** Installed compatible Python (prefer 3.11), standard library, NumPy, SciPy, pytest. MLX LM and a Docker-compatible local engine first appear at M1.

**Spec:** [Project specification](../specs/2026-09-29-dependency-aware-verification-design.md). Read it with this plan; its research gates and scope remain binding.

**Starting state:** Empty Git repository apart from these planning documents; no package, dependencies, model/image revisions, task corpus, or measured machine profile yet. M0 is unexecuted.

## Global constraints

- Build only the next milestone. M0 permits no model downloads, model calls, MLX installation, real candidate execution, or benchmark expansion.
- Use the standard library, NumPy, SciPy, and pytest; add `mlx-lm` at M1 and import it lazily.
- One resident LLM, one concurrent request; 3,072 input tokens, 512 proposal output tokens, 128 review output tokens, 4,096 maximum context.
- Four checks `(R1, R2, T, D)`, each at most once; verdicts `PASS`, `FAIL`, `UNKNOWN`; separate `NOT_ACQUIRED` history state; terminals `ACCEPT`, `DEFER`.
- Candidate caps: 1 CPU, 512 MiB, 32 processes, 10 seconds, combined stdout/stderr 64 KiB; model-call cap 180 seconds.
- M1/M2/M3/M4/M5 model-active caps: 15 minutes / 60 minutes / 4 hours / 3 hours / 2 hours; total 12 hours including failed/repeated calls.
- Stage forecasts use measured work with a 1.5× margin; reserve timeout allowance before a call; insufficient stage allowance checkpoints/stops the stage.
- Natural splits: 24 pilot, 96 train, 48 development, 128 locked test; 296 episodes, 74 intended root groups; four variants per root are clustered.
- Wrong-accept penalty 20, defer penalty 5, latency unit median warm pilot R1 seconds; training-only predicted action costs; replay charges selected original measured costs.
- Fit alpha from `{4, 16, 64}` equally for I/P/J; generic pair uses four training-only root folds and alpha=16 for structure selection.
- Freeze test task/source/split definitions before M3; freeze fitted run before M4 proposals; no test-label or future-outcome policy input.
- No host execution fallback, repair loop, favorable retries, public-test removal, artificial sleeps, threshold changes, or compute upgrade to rescue the hypothesis.
- No generic gate-bypass flag. A research stop still produces a report and preserves all artifacts available at that point.

## Review focus

These boundary cases are easy to miss in a happy-path M0 implementation; each is assigned below.

1. NaN/infinity, negative time, duplicate JSON keys, or contradictory public-FAIL labels must not become usable probabilities/evidence — Tasks 1, 3, 5.
2. An unavailable check and an attempted UNKNOWN check must remain distinct, including a zero-cost action — Tasks 4, 6.
3. A symlink or changed protected file between preflight and apply must refuse installation without touching the source checkout — Task 2.
4. A crash after reservation or a repeated resume must retain incurred work without billing complete evidence twice — Task 7.
5. All deferrals or a single root with many variants must not create zero loss, zero cost per success, or fictitious precision — Task 8; bootstrap extension at M3/M4.

## File structure and task order

The following files are the intended M0 implementation, **not files to scaffold while writing this plan**:

| Path | Owner / purpose |
| --- | --- |
| `pyproject.toml`, `requirements.lock`, `.gitignore` | Task 1: package/test setup, verified core pins, ignore generated files |
| `src/depverify/__init__.py`, `records.py` | Task 1: record types, enums/type aliases, strict JSON and hashing |
| `tasks.py` | Task 2: fake public task staging, mechanical preflight, safe apply/defer, group checks |
| `probability.py` | Task 3: table validation and exact queries, with no fitted estimator yet |
| `policy.py` | Task 4: exact planner and initial constant/test-only policies |
| `checks.py`, `runner.py` | Task 5: strict parsing, deterministic fake adapters; no real execution |
| `evaluate.py` | Task 6: masked replay; Task 8: accounting, controls, basic metrics |
| `pipeline.py`, `config.toml` | Task 7: ledger/gates; Task 8: fake orchestration |
| `__main__.py`, `README.md` | Task 8: currently implemented commands and setup |
| `tests/conftest.py`, `tests/test_*.py` | Owning tasks: deterministic fixtures and independent assertions |
| `reports/m0.md` | Task 9: measured M0 evidence and next permitted milestone |

Task dependency order is 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9. This linear order is intentional; interfaces are small and shared. Implement natively unless a later execution request chooses delegation. If the execution environment requires isolation, use the Superpowers worktree skill at execution time; do not make an empty-repository worktree subsystem part of this project.

Each task uses red → green → relevant regression tests → a focused commit. Setup and documentation belong with the first tested deliverable needing them. Do not write real adapters, count fitting, or later CLI stubs during M0.

## M0 executable plan

### Task 1: establish records and reproducible core package

**Files:** Create `pyproject.toml`, `requirements.lock`, `.gitignore`, `src/depverify/__init__.py`, `src/depverify/records.py`, `tests/test_records.py`, `tests/conftest.py`.

**Interfaces:**

- Export string-literal type aliases `Verdict`, `TerminalAction`, `CheckId`, `Lineage`; `CHECK_IDS=("R1","R2","T","D")`, `VERDICTS=("PASS","FAIL","UNKNOWN")`.
- `History = tuple[str | None, str | None, str | None, str | None]`; `None` means NOT_ACQUIRED. Validate exact length and allowed values at boundaries.
- Dataclasses carry the specification's fields; group version/cost metadata in validated dictionaries to keep signatures manageable. Required constructor fields are:

```text
Task(episode_id: str, root_group_id: str, split: str, task_class: str,
     contract: str, editable_path: str, entry_point: str,
     base_files: dict[str, str], public_tests: tuple[dict, ...],
     source_manifest: dict)
Proposal(episode_id: str, proposal_key: str, replacement: str,
         status: str, actor: dict, preflight_seconds: float)
CheckResult(proposal_key: str, check_id: str, verdict: str, status: str,
            reason: str, elapsed_seconds: float, metadata: dict)
Decision(proposal_key: str, policy_hash: str,
         history: tuple[tuple[str, str], ...], action: str, status: str,
         selected_check_seconds: float, controller_seconds: float,
         wrapper_seconds: float)
GateResult(stage: str, status: str, recorded_at: str, artifact_hashes: dict,
           criteria: dict, reasons: tuple[str, ...], evidence_paths: tuple[str, ...],
           budget_snapshot: dict)
```

- All serialized records have `schema_version=1`. `actor`/check metadata must validate the explicit revision, seed, prompt/source/environment hashes, token counts, timeout/cache flags and attempt fields from spec §5; fake identities are visibly `fake`, never real revision claims.
- `canonical_json(value: object) -> bytes`, `sha256_bytes(data: bytes) -> str`, `proposal_key(task: Task, replacement: str, environment: dict, check_versions: dict) -> str`.
- `read_json(path: Path) -> object`, `write_json_atomic(path: Path, value: object) -> None`, `append_event(path: Path, event: dict) -> bool` (False for an identical already-recorded ID; conflicting duplicate raises `ValueError`).

- [ ] **Step 1: Write the record tests before implementation.** Assert a dataclass round trip; every hash input changes the proposal key; JSON dict insertion order does not; replacement bytes remain significant; hidden label/condition fields cannot enter `Task`; negative/non-finite time/token values and unknown schemas fail. Include literal assertions:

```python
assert canonical_json({"b": 2, "a": 1}) == b'{"a":1,"b":2}'
with pytest.raises(ValueError):
    canonical_json({"elapsed_seconds": float("nan")})
assert key_with_new_environment != original_key
assert key_with_new_source != original_key
```

- [ ] **Step 2: Create minimal packaging needed to run the failing tests.** Declare only core/test dependencies, choose an actually installed supported interpreter, and install into a project virtual environment. Record real resolved core versions, including transitives; do not write speculative MLX pins. Add ignores for `.venv/`, caches, and `runs/`. Run `python -m pip install -e '.[dev]'`, then `python -m pytest tests/test_records.py -q`; expect failure for missing record implementations, not an unexplained environment failure.
- [ ] **Step 3: Implement the listed record, hash, strict JSON, and atomic-write functions.** Reject duplicate JSON keys and non-finite numbers. Preserve raw bytes through hashes; JSONL stable IDs make identical appends idempotent. Clone/freeze mutable inputs on record construction so external mutation cannot change stored identities.
- [ ] **Step 4: Run `python -m pytest tests/test_records.py -q`.** Expect all record tests to pass; inspect the lock file and installed distributions to confirm there is no MLX dependency.
- [ ] **Step 5: Commit only this task's package and record files.** Suggested message: `feat: add validated experiment records and identities`.

### Task 2: enforce public-task and disposable-file boundaries

**Files:** Create `src/depverify/tasks.py`, `tests/test_tasks.py`; extend fake fixtures in `tests/conftest.py`.

**Interfaces:**

- Consumes `Task`, `Proposal`, and canonical hash helpers from Task 1.
- `validate_splits(tasks: Sequence[Task]) -> None` rejects root overlap between splits; all variants/repeats retain root identity.
- `materialize(task: Task, parent: Path) -> Path` creates a fresh disposable directory containing only its allowed public files.
- `preflight(task: Task, replacement: str, candidate_root: Path) -> tuple[str, dict]` returns a mechanical status and protected-hash manifest without executing the replacement.
- `apply_or_defer(task: Task, proposal: Proposal, action: str, candidate_root: Path, expected_identity: dict) -> dict` returns status, wrapper time, and before/after file hashes; revalidates all identities and installs only the approved bytes for ACCEPT.

- [ ] **Step 1: Write tests for safe ACCEPT, unchanged DEFER, syntax/entry-point errors, >64 KiB replacement, absolute/traversal paths, symlink escapes, changed protected files, stale proposal/environment, and duplicate apply.** Use `tmp_path` only. Assert the original fixture tree is byte-identical afterward, no file outside the disposable root changed, and a repeat of the same accepted proposal creates no additional change. Treat Python text that would raise if executed as inert during preflight.

```python
assert after_original_hashes == before_original_hashes
assert deferred_copy_hashes == base_copy_hashes
assert accepted_copy_hashes["candidate.py"] == sha256_bytes(replacement.encode())
assert status_for_changed_support == "stale_identity"
with pytest.raises(ValueError):
    validate_splits([train_variant, test_variant_of_same_root])
```

- [ ] **Step 2: Run `python -m pytest tests/test_tasks.py -q`.** Expect missing implementations to fail.
- [ ] **Step 3: Implement these functions in `tasks.py`.** Resolve and verify path containment, reject symlink components, parse using `ast.parse`, inspect expected entry-point shape, compare protected manifests again immediately before atomic installation. This host wrapper never imports or runs candidate Python. Failed preflight yields invalid proposal/DEFER with measured cost.
- [ ] **Step 4: Run `python -m pytest tests/test_records.py tests/test_tasks.py -q`.** All tests pass, including protected-file mutation between validation and apply.
- [ ] **Step 5: Commit this tested boundary.** Suggested message: `feat: restrict proposals to disposable allowlisted files`.

### Task 3: implement coherent known-table probability queries

**Files:** Create `src/depverify/probability.py`, `tests/test_probability.py`; add deterministic table builders to `tests/conftest.py`.

**Interfaces:**

- Consumes `History` and ordered IDs/verdicts.
- `validate_joint(joint: np.ndarray) -> None` validates shape `(2,3,3,3,3)`, finite nonnegative mass, sum within `1e-12` of 1, and zero `Y=1,T=FAIL` mass.
- `history_mass(joint: np.ndarray, history: History) -> float` sums compatible cells.
- `posterior_correct(joint: np.ndarray, history: History) -> float` returns conditional Y=1 probability; zero support raises a named `ZeroSupportError`.
- `predictive(joint: np.ndarray, history: History, check_id: str) -> np.ndarray` returns three probabilities for an unqueried check from that same distribution.
- JSON/NPZ loading validates schema/check order/version before returning tables; use `allow_pickle=False`.

- [ ] **Step 1: Write normalization, marginalization, total-probability, copied-review, unknown-support, and invalid-distribution tests.** Build a copied-review table with prior .5, R1 accuracy .8, R2=R1, T/D always UNKNOWN. Assert:

```python
assert posterior_correct(joint, (None, None, None, None)) == pytest.approx(.5)
assert posterior_correct(joint, ("PASS", None, None, None)) == pytest.approx(.8)
assert posterior_correct(joint, ("PASS", "PASS", None, None)) == pytest.approx(.8)
assert predictive(joint, ("PASS", None, None, None), "R2").tolist() == [1., 0., 0.]
assert sum(branch_probability * branch_posterior for branch_probability,
           branch_posterior in supported_branches) == pytest.approx(parent_posterior)
```

Also assert malformed shapes, NaN, negatives, nonunit totals, executable object arrays, and positive `Y=1,T=FAIL` mass are rejected. Missing support is not automatically posterior .5.
- [ ] **Step 2: Run `python -m pytest tests/test_probability.py -q`.** Expect missing functions to fail.
- [ ] **Step 3: Implement exact indexed summation in `probability.py`.** No fitted estimators, approximations, embeddings, model libraries, or task-class features. Test fixtures construct probabilities independently of these marginalization helpers.
- [ ] **Step 4: Run `python -m pytest tests/test_probability.py -q`.** All assertions pass; independent direct cell sums agree within `1e-12`.
- [ ] **Step 5: Commit the probability interface.** Suggested message: `feat: add coherent finite evidence distributions`.

### Task 4: implement exact finite-horizon decisions and controls

**Files:** Create `src/depverify/policy.py`, `tests/test_policy.py`, `tests/test_policy_controls.py`.

**Interfaces:**

- Consumes validated joint arrays and Task 3 queries.
- `plan(joint: np.ndarray, history: History, available: frozenset[str], costs: Mapping[str, float], *, wrong_accept: float = 20., defer: float = 5.) -> tuple[str, float]` returns next action and expected future cost; acquisition actions use their check IDs.
- `make_policy(tables: Mapping[str, np.ndarray], costs: Mapping[str, float], *, wrong_accept: float = 20., defer: float = 5.) -> Callable[[str, frozenset[str], History], tuple[str, str]]` validates/fixes inputs and memoizes the recursion; the callback accepts only lineage, availability, and acquired history, and returns `(action, status)`. Invalid calibration or zero support returns `("DEFER", "calibration_invalid")` or `("DEFER", "zero_support")`; normal choices have status `ok`. Status is an output diagnostic, not an extra policy feature.
- `always_accept`, `always_defer`, `test_only` use the same callback signature and `(action, status)` result; common preflight and public-FAIL veto wrap every policy.

- [ ] **Step 1: Write independent expected-value controls and tie assertions.** Use fixed finite distributions, not model results. Required scenarios: independence, exact copies, informative mixed checks, all useless, free perfect, expensive perfect, asymmetric rates, complementary XOR-like checks, zero support, missing actions, all UNKNOWN, and zero-cost redundant actions. Key expected values:

```python
assert plan(useless, empty, all_actions, positive_costs) == ("DEFER", 5.)
action, value = plan(free_perfect_r1, empty, frozenset({"R1"}), {"R1": 0.})
assert action == "R1"
assert value == pytest.approx(2.5)  # prior .5: accept correct; defer incorrect
action, value = plan(xor_pair, empty, frozenset({"R1", "R2"}), {"R1": .1, "R2": .1})
assert action == "R1"
assert value == pytest.approx(2.7)  # neither singleton informative; pair is perfect
assert plan(prior_point_75, empty, frozenset(), {}) == ("DEFER", 5.)
```

For the XOR fixture, Y is whether two equiprobable binary verdicts agree; T/D are UNKNOWN. A costly redundant copy loses to stopping. A public FAIL history always defers.
- [ ] **Step 2: Run `python -m pytest tests/test_policy.py tests/test_policy_controls.py -q`.** Expect missing planner failures.
- [ ] **Step 3: Implement the exact recursion with the spec's deterministic tie order.** Memoize immutable histories/masks per fixed table and cost setting. Reject non-finite/negative costs; skip zero-probability branches without inventing posteriors. Each branch adds exactly one previously unacquired action.
- [ ] **Step 4: Add an independent exhaustive trajectory scorer to the tests.** For each positive-mass full `(Y,outcomes)` cell, execute the callback with a locally masked history, accumulate realized action/terminal loss, and probability-weight the sum. Assert this equals DP value. Iterate all 256 histories and 16 availability masks, treating impossible histories as safe DEFER; assert finite values and at most four acquisitions. For the positive coupling control, compare the XOR table above to its conditionally independent R1/R2 product: each singleton has the same .5/.5 marginal in both Y classes, but the true pair planner costs 2.7 versus 5 for the independent planner's deferral. For the no-gain control, set both toy action costs to 3: both planners defer with loss 5. These fixtures hold marginals fixed and demonstrate both a policy change and its economic limit; their toy costs never change the real protocol.
- [ ] **Step 5: Run `python -m pytest tests/test_probability.py tests/test_policy.py tests/test_policy_controls.py -q`.** All controls pass, including the exhaustive comparison and no-gain case.
- [ ] **Step 6: Commit the tested planner.** Suggested message: `feat: plan exact bounded evidence acquisition`.

### Task 5: add strict check parsing and inert fake adapters

**Files:** Create `src/depverify/checks.py`, `src/depverify/runner.py`, `tests/test_checks.py`, `tests/test_fake_runner.py`.

**Interfaces:**

- `parse_review(raw: str, *, truncated: bool = False) -> tuple[str, str, str]` returns `(verdict,status,reason)`; uses strict JSON from Task 1.
- `FakeRunner(responses: Mapping[str, dict]).run(proposal_key: str, inputs: Sequence[object]) -> dict` returns registered JSON-compatible results and counters. It never evaluates candidate source or spawns a process.
- `fake_check(proposal: Proposal, check_id: str, fixture: dict) -> CheckResult` returns deterministic verdict/status/measured-fixture cost; no sleeps.
- `check_cache_key(proposal: Proposal, check_id: str, prompt: bytes, settings: dict, sources: dict) -> str` covers all spec §5 identities. M0 tests identity invalidation; real caching arrives only with real collection.

- [ ] **Step 1: Write parser tests for the exact object, invalid JSON, extra prose/keys, duplicate keys, wrong types, unknown verdict, refusal, and truncation even when the text looks parseable.** Assert invalid cases return UNKNOWN with explicit status and never fabricate PASS. Test candidate failure versus infrastructure failure mappings separately. Fake elapsed values survive unchanged without sleeping.

```python
assert parse_review('{"verdict":"PASS","reason":"Matches."}') == ("PASS", "ok", "Matches.")
assert parse_review('PASS')[0] == "UNKNOWN"
assert parse_review('{"verdict":"PASS","reason":"x"}', truncated=True)[0] == "UNKNOWN"
assert changed_seed_key != original_key
assert changed_tokenizer_revision_key != original_key
```

- [ ] **Step 2: Run `python -m pytest tests/test_checks.py tests/test_fake_runner.py -q`.** Expect missing adapters to fail.
- [ ] **Step 3: Implement parser and fake adapters.** Keep fake runner visibly fake; tests monkeypatch subprocess/candidate-execution entry points to fail if called. Genuine independent R1/R2 action IDs stay distinct even with identical returned bytes. Do not create `local_model.py` or Docker code yet.
- [ ] **Step 4: Run `python -m pytest tests/test_checks.py tests/test_fake_runner.py -q`.** All expected mappings, inert execution, and cache-key invalidation tests pass.
- [ ] **Step 5: Commit these adapters.** Suggested message: `feat: add strict evidence parsing and fake checks`.

### Task 6: enforce masked replay and label isolation

**Files:** Create `src/depverify/evaluate.py`, `tests/test_replay.py`, `tests/test_data_isolation.py`.

**Interfaces:**

- `replay_episode(proposal: Proposal, lineage: str, available: frozenset[str], policy: Callable, evidence: Mapping[str, CheckResult], *, policy_hash: str) -> Decision` owns full evidence on the trusted side; calls the Task 4 callback with only lineage, available actions, and acquired verdict history, consuming its `(action, status)` result.
- Internal `request(check_id: str) -> str` returns only verdict; charges once to a trusted ledger. Duplicate/unavailable requests raise `ValueError` before a second side effect or charge.
- No labels argument exists here. Private labels are joined in the later scoring function after replay completes. Decision status records protocol/calibration failures and safely defers.

- [ ] **Step 1: Write tests changing each unrequested outcome while fixing acquired history and policy tables.** Assert the next action remains identical. Separately perturb every test label and assert all trajectories are byte-identical, including selected checks. A spy policy must observe no IDs/class/raw reason/raw output/timing/full-table/label fields.

```python
assert next_action(original_unseen) == next_action(perturbed_unseen)
assert trajectories_before_label_edit == trajectories_after_label_edit
assert decision.selected_check_seconds == pytest.approx(12. + 3.)
assert double_request_execution_count == 1
assert double_request_charged_seconds == 12.
```

Include unavailable D versus acquired D=UNKNOWN, earlier hidden T=FAIL unavailable to policy, acquired T=FAIL veto, equal review bytes charged for two genuine actions, fresh fake state per check, and no use of tiny cache lookup time as replay cost.
- [ ] **Step 2: Run `python -m pytest tests/test_replay.py tests/test_data_isolation.py -q`.** Expect missing replay interface to fail.
- [ ] **Step 3: Implement trusted access and bounded policy execution.** The callback receives no accessor object that exposes full records. Validate requested action against available/unacquired IDs; cap at four; preserve actual acquired histories. Replay uses fixed check results, never fitting or hidden grading.
- [ ] **Step 4: Run `python -m pytest tests/test_replay.py tests/test_data_isolation.py tests/test_policy.py -q`.** All perturbation, duplicate, cost, and termination assertions pass.
- [ ] **Step 5: Commit replay isolation.** Suggested message: `feat: mask replay evidence and isolate correctness labels`.

### Task 7: implement stage gates and auditable budget reservations

**Files:** Create `src/depverify/pipeline.py`, `config.toml`, `tests/test_budget.py`, `tests/test_gates.py`, `tests/test_resume.py`; extend record helpers only as needed.

**Interfaces:**

- Ledger events are strict JSON dictionaries keyed by run/stage/episode/check/attempt/event ID; budgets use seconds and distinguish model-active work from execution/wall work.
- `reserve(ledger_path: Path, *, attempt_id: str, stage: str, work_kind: str, allowance_seconds: float, limits: dict) -> str` atomically records a reservation or raises `BudgetStop` before any call.
- `settle(ledger_path: Path, *, reservation_id: str, actual_seconds: float, status: str) -> None` retains actual incurred cost and releases unused reserved allowance; identical repeat settlement is idempotent, conflicting settlement blocks.
- `require_gate(gate_path: Path, *, stage: str, expected_hashes: dict) -> GateResult` accepts only current GO, rejecting absent/failed/stale gates.
- `write_gate(path: Path, result: GateResult) -> None` preserves prior immutable gate records; `resume_attempts(ledger_path: Path) -> dict` reconciles complete/in-flight events with at most one infrastructure retry.

- [ ] **Step 1: Write boundary tests with a fake monotonic clock.** A 180-second model reservation must fail with 179 seconds remaining and launch zero calls. Reserve 180 and settle 12 to bill 12 and release 168; container work cannot debit model-active budget. Failed/repeated attempts retain both costs. A crash after reservation cannot become free completed work; repeated resume cannot duplicate evidence/billing. Test every non-GO/missing/stale gate, counters for one pilot revision/one mechanism revision, and no gate bypass configuration.

```python
with pytest.raises(BudgetStop):
    reserve_with_remaining(179., requested=180.)
assert calls_launched == 0
assert settled_actual == 12.
assert released_allowance == 168.
assert charged_after_second_resume == charged_after_first_resume
```

- [ ] **Step 2: Run `python -m pytest tests/test_budget.py tests/test_gates.py tests/test_resume.py -q`.** Expect missing ledger/gate behavior to fail.
- [ ] **Step 3: Implement reservations and gate validation without a scheduler/database.** Copy spec caps into `config.toml`. Unreconciled running attempts keep their reservation or conservatively incur it; do not make up a precise duration. Trailing partial records are preserved/repaired explicitly. Stage exhaustion checkpoints; per-proposal forbidden actions defer. Timing estimates are absent/unavailable until measured, never invented zeroes.
- [ ] **Step 4: Run `python -m pytest tests/test_budget.py tests/test_gates.py tests/test_resume.py tests/test_records.py -q`.** All accounting/resume tests pass under both interrupted and complete event sequences.
- [ ] **Step 5: Commit budget and gate controls.** Suggested message: `feat: enforce milestone gates and work budgets`.

### Task 8: integrate fake CLI flow, core scenarios, and loss accounting

**Files:** Create `src/depverify/__main__.py`, `tests/test_cli.py`, `tests/test_pipeline.py`, `tests/test_accounting.py`; extend `evaluate.py`, `pipeline.py`, `README.md`.

**Interfaces:**

- `main(argv: Sequence[str] | None = None) -> int` implements only currently supported `doctor --fake`, `simulate --suite core`, and `report`. Later commands are added by their milestone; unknown commands exit with a clear argparse error and no side effects.
- `run_fake_episode(task: Task, replacement: str, evidence: Mapping[str, CheckResult], policy: Callable, parent: Path) -> tuple[Proposal, Decision]` composes preflight, replay, and safe apply/defer; fake runner never executes code.
- `score_decision(proposal: Proposal, decision: Decision, label: int | str, *, unit_seconds: float, wrong_accept: float = 20., defer: float = 5.) -> dict` performs the post-decision private label join and loss arithmetic. Unresolved labels get a separate status, no optimistic loss.
- `summarize(rows: Sequence[dict]) -> dict` produces raw counts, root-weighted means, cost-per-correct-accept or explicit undefined value, selected check counts, and denominator ledger.
- `run_core_suite(run_dir: Path) -> dict` executes named deterministic controls, stores expected/actual values, code/config hashes, fake eligibility marker, and evidence paths; `render_report(run_dir: Path) -> str` can summarize any completed prefix.

- [ ] **Step 1: Write subprocess CLI tests using a temporary working directory and only fake inputs.** Assert fake doctor succeeds without MLX/Docker imports or network; core simulation records all required scenarios, zero model work, and deterministic decisions. End-to-end fixtures produce both ACCEPT and DEFER, malformed proposals remain in the denominator, research original files never change, and output artifacts stay under the declared run/temp directory.
- [ ] **Step 2: Write independent loss/denominator assertions.** With unit=2, actor=8, preflight=2, acquired=4, controller=1, wrapper=1 seconds, base work is 8 units. Correct accept loss=8, incorrect accept=28, defer=13. Test all-defer cost-per-correct is undefined/infinite and loss remains positive, and one root's duplicated variants do not change equal-root weighting.

```python
assert correct_accept_loss == 8.
assert incorrect_accept_loss == 28.
assert defer_loss == 13.
assert all_deferred["correct_accepts"] == 0
assert all_deferred["seconds_per_correct_accept"] is None
assert replicated_within_root_mean == original_equal_root_mean
```

Use `None` plus an explicit `undefined_no_correct_accepts` status in JSON instead of illegal Infinity. Validate positive pilot unit, no NaN rates, and reconciliation of common/selected/research costs.

- [ ] **Step 3: Run `python -m pytest tests/test_cli.py tests/test_pipeline.py tests/test_accounting.py -q`.** Expect absent CLI/integration/scoring functions to fail.
- [ ] **Step 4: Implement only the composed M0 flow.** Keep argparse thin. `simulate` produces evidence, not a research success claim or an automatic M1 launch. README gives actual installation/fake commands, current scope, and how to inspect run records. Initial `report` says M0 implementation evidence only and later stages unexecuted.
- [ ] **Step 5: Run `python -m pytest tests/test_cli.py tests/test_pipeline.py tests/test_accounting.py -q`, `python -m depverify doctor --fake`, and `python -m depverify simulate --suite core`.** All complete with finite reconciled values, no MLX/model/container work, and at most four acquisitions per proposal.
- [ ] **Step 6: Commit fake integration.** Suggested message: `feat: run and account for fake verification episodes`.

### Task 9: verify M0, record its gate, and stop at the next boundary

**Files:** Extend `README.md`; create `reports/m0.md`; generate ignored `runs/m0/` evidence/ledger/gate files. Fix only demonstrated M0 defects.

**Interfaces:** Consumes the stable package/CLI, `run_core_suite`, `GateResult`, `write_gate`, and all tests. No new domain API or real adapter.

- [ ] **Step 1: Inspect changes and the spec-to-test checklist.** Confirm each M0 concern in spec §13 has a concrete test; no later scaffolding, benchmark dataset, executable candidate evaluation, or MLX dependency has appeared. Confirm core-package pins were resolved on the actual interpreter.
- [ ] **Step 2: Run fresh verification with code/config fingerprints captured before and after.** Execute these exact checks from the package environment, capture exit codes and output paths, and reject a changed source fingerprint:

```bash
python -m pip check
python -m depverify doctor --fake
python -m depverify simulate --suite core
python -m pytest -q --junitxml=runs/m0/pytest.xml
git diff --check
```

Expected: dependency check reports no broken requirements; fake doctor and every core control pass; pytest exits zero; no whitespace errors. A command not run or a stale result cannot be recorded as passing. The final gate binds the hash of these captured results and the unchanged code/config fingerprint. Use a short trusted verification invocation of `write_gate` after inspecting all results; do not let a successful `simulate` alone certify unrelated pytest checks.

- [ ] **Step 3: Create the M0 `GateResult`.** Set GO only if mathematics, controls, masking, file permissions, termination, and accounting all pass. Otherwise record BLOCKED with failing evidence and repair before re-verification. Record zero model calls/downloads and zero model-active time. Gate creation does not execute M1.
- [ ] **Step 4: Write `reports/m0.md` from observed results.** Include commands, counts actually run, control expected/actual values, scope limits of fakes, hash-linked artifacts, gate status, and the next permitted milestone. Do not copy the brief's claimed 16 checks or toy loss numbers as this run's results. If permanently blocked, finish an INCONCLUSIVE report with BLOCKED execution and mark later stages unexecuted.
- [ ] **Step 5: Commit the verified M0 deliverable.** Suggested message: `test: verify M0 controls and record gate evidence`. Preserve generated evidence outside Git with a manifest; commit only compact summaries and reproducibility instructions. At execution time, provide a self-contained result and apply the next-milestone rule.

## Conditional roadmap: refine only the next permitted milestone

This roadmap covers the whole project without pretending future timings, revisions, source designs, or natural error rates are known. Each stage requires a concrete next-milestone task plan based on the preceding evidence. Preserve the spec's numbers and stop rules; a later planning pass cannot loosen them. Run ordinary tests appropriate to each change, then the milestone checks; stop after a failed research gate and finish M6.

### M1 — local execution envelope (requires current M0 GO)

**Files:** Add `src/depverify/local_model.py`, `prompts/{actor,r1,r2,d}.txt`, pilot public/private materials and source manifests, `tests/test_local_model.py`, `tests/test_runner.py`, `tests/test_evaluator.py`; extend `runner.py`, `checks.py`, `tasks.py`, `pipeline.py`, CLI, lock/config, README; write `reports/m1.md`.

**Work packages:**

1. Define the six pilot roots/four contract variants each, references, boundary/randomized/regression/invariant checks, and boundary/constant/public-example mutants. Keep hidden expected behavior on the trusted host; evaluator gives the candidate inputs only. Validate root identities and source lineage from manifests; no proposal collection yet.
2. Implement `doctor --local`: read architecture/RAM/macOS/disk/power, find the installed engine, verify native ARM64 support, resource reserve `max(8 GiB, .25 × RAM)`, and a 20 GiB free-space target plus actual needs. Freeze a pressure sampling and sustained-swap rule before calls. No privileged tuning.
3. Resolve and record immutable model/tokenizer revision and ARM64 Python image digest; install MLX only now. Implement one serial worker with exact token counting/chat template, 180-second outer kill/restart, safetensors and remote-code prohibition, fixed seeds/temperatures, no shared conversation/KV context. Record successful package pins; resource fallback is a separate logged setting.
4. Replace only real runner functionality with digest-pinned container execution using every spec flag. Stream bounded outputs, enforce 10-second outer deadline, remove by tracked ID/run-owned identity even after launch interruption, bound engine logs, and verify cleanup. Candidate/source text never enters shell interpolation.
5. Freeze a small smoke/repeat manifest, run ordinary proposal/review calls after warm-up, collect load/prompt/output/memory/overhead timing, parser rates, and rerun text-versus-verdict stability. Count all warm-up/failures/repeats within 15 minutes. Forecast all M2 work including eager grounding using 1.5× margin.

**Required tests/evidence:** actual infinite loop, flood, subprocess, network, home-read, protected-write fixtures; container mounts contain no private canaries/references/expected outputs; public/private invocations separate; absence of engine means BLOCKED without host fallback; exact token-boundary tests and no prompt truncation; all ordinary smoke tasks; at least 90% review parses. Run `doctor --local`, `smoke --config config.toml`, ordinary/runner tests, and record M1 gate.

**Stop:** resource/setup/isolation/parser/termination defect is BLOCKED; adjust only before freeze within allowed small setting, never buy compute. Do not start M2 unless the forecast fits.

### M2 — natural pilot and headroom (requires M1 GO)

**Files:** Extend `pipeline.py`, `evaluate.py`, `policy.py`, CLI, pilot manifests, tests for collection/resume/eager separation; write `reports/m2.md` and immutable pilot records.

**Work packages:**

1. Implement `collect --split pilot --resume --dry-run` and normal collection: strict preflight, exact prompt/cache identities, gate/budget checks, balanced check orders, independent seed schedule, complete immutable attempts, private labels kept separate. Dry-run shows 24 episodes, 21,504 core output-token ceiling, additional eight grounding-actor outputs (up to 4,096), measured estimate, budgets, and prerequisite gate; input costs remain measured separately.
2. Freeze the eight eager-grounding IDs and manual trace IDs before outcomes. Collect one proposal and all available checks per valid natural episode; do not replace malformed or incorrect outputs. Grounding alternative receives all allowed docs and runs T against its own proposal, with extra input processing charged.
3. Implement pilot simple/fixed-policy analysis and evidence matrix; use exploratory pilot tables only for screening, clearly separate from later train-fit models. Show T-passing wrong patches, complementary catches by root/check type, natural malformed/error split, source lineage, costs, and strongest cheap workflow. Audit declared traces and all inconsistencies.
4. Produce each of the six explicit GO criteria, planned next-stage forecast, and ledger reconciliation in a short gate record. Require five correct/five incorrect natural proposals, complementary useful checks across at least three roots, and relevant evidence against at least one wrong public-PASS proposal.

**Required tests/evidence:** interrupted collect/resume without duplicate work, infrastructure-only one retry, malformed outputs retained, unresolved labels >2% block, hidden-public contradiction blocks, source truth never a feature, genuine duplicate action handling, missing versus UNKNOWN, no T latency inflation, eager system not paired by patch. Commands: `collect --split pilot --resume`, `evaluate --stage pilot`, relevant pytest suite.

**Stop:** dominant cheap workflow/redundant checks/mostly malformed failure is NO_GO. Scarcity/diversity is INCONCLUSIVE; only one documented fresh-root 24-episode replacement is possible inside the same 60-minute/total budgets. Preserve the first pilot and excluded status; do not generate favorable errors.

### M3 — fit and challenge (requires M2 GO)

**Files:** Extend public/private benchmark manifests, `probability.py`, `policy.py`, `evaluate.py`, `pipeline.py`, CLI; add fitting/baseline/selection/grouped-statistics/locking tests; create `reports/m3.md`, policy tables and support artifacts.

**Work packages:**

1. Extend to 24 train, 12 development, and 32 test root groups with four variants each; conservatively merge shared templates. Validate all references/mutants/contracts without model proposals, reserve transfer class, then lock split/task/source hashes before M3 fitting/collection. If independent roots are unavailable, record the smaller exploratory design and stop confirmatory expansion.
2. Forecast and collect 96 train + 48 development episodes within four hours; require at least 20 correct and 20 incorrect mechanically valid training proposals and disclose complete table support. No rebalance, synthetic substitution, or automatic expansion.
3. Implement `fit_tables(rows, model, alpha)` in `probability.py` for I/P/J and configurable pairs with the exact priors/backoffs/structural T zero. Fit predicted costs only from training medians; freeze pilot unit. Add lineage-free P ablation. Unknown group/backoff is explicit; wrong versions invalidate calibration.
4. Implement every baseline in spec §11, including all 24 restricted orders, source deduplication, learned single-outcome maps, generic learned pair (six pairs, four grouped training folds, alpha=16 for log-loss structure choice), all-checks costed diagnostic, and optional labeled oracle. Tune each alpha using only the same three development choices. Record support/parameter count/CPU fitting work.
5. Add root-level paired bootstrap/statistical/economic reports needed to challenge the mechanism, using fixed resampling seed and 10,000 paired blocks. Test zero-denominator/degenerate ratios, raw-count guardrails, cloned-root weighting, exact group-level intervals, cold/warm costs, and break-even arithmetic.
6. Select the eligible baseline champion using minimum dev objective and preregistered practical tie rule; compare P with champion, I, J, generic pair, deduplication, and lineage-free P. Freeze complete policy definitions and final test feasibility when every M3 criterion passes.

**Required tests/evidence:** backoff distributions normalize with sparse/zero counts; coherent posterior/predictive; contradictory T labels block; all algorithms see equal rows/metadata/planner/costs; grouped folds cannot leak roots; no train/dev mix in parameter/cost fits; source-only shortcut fails dependence claim; champion cannot select P or a diagnostic; bootstrap preserves paired roots; no fake efficiency for all-defer. Commands: train/dev collect with dry-runs/resume, `fit`, `evaluate --stage dev`, full appropriate tests.

**Stop:** <10% mean-loss improvement, quality regression, no dependence-removal effect, effect confined to one root, or sufficient simple/generic alternative blocks advancement under the stated NO_GO/INCONCLUSIVE rules. One substantive documented mechanism revision maximum; never tune on locked test.

### M4 — locked local evaluation (requires M3 GO and frozen run)

**Files:** Extend freeze/evaluation CLI and `pipeline.py`, `evaluate.py`; add locked-evaluation tests; create `frozen_run.json` under the run and `reports/m4.md`.

**Work packages:**

1. Implement `freeze` to validate current code/config/task/split/source/model/tokenizer/image identities, all policies and champion, smoothing/costs/unit, primary penalties, seeds, sample size, repeat/timing rules, and gates. A dirty but fingerprinted checkout must not silently differ from what the manifest records; archive the exact evaluated source or require a clean recorded commit.
2. Dry-run and collect 128 held-out proposals/check sets within three hours, with no fitting or outcome inspection driving changes. Require `--locked` evaluation and reject missing/changed freeze identities. Policy replay remains label-blind; score only afterward on common eligible episodes.
3. Produce the complete metric table and every baseline, root-weighted loss/time ratios with 10,000 paired resamples, descriptive 95% intervals, adjusted one-sided 97.5% bounds for P−champion and P−I (deduplicate if identical), quality counts, support, class-group sensitivity, prediction diagnostics, and denominator ledger.
4. Apply all seven spec §14 M4 conditions, including ≥10% loss and time-per-correct savings, no observed quality regression, ≥20 correct accepts over ≥8 roots, mechanism comparison, and complete-table domination check. Replay the nine economic sensitivities without retuning or changing the primary result. Record deployment/research/outcome-cost separation and break-even scenarios.

**Required tests/evidence:** changing any test label cannot change any policy trajectory/fit/cost estimates; mutated lock inputs reject collection; test fitting is unreachable; zero-success resamples are retained as non-estimable, not dropped; quality guardrails use common denominators including malformed proposals; no test runner-up cherry-picking; intervals use root means rather than variants. Commands: `freeze`, `collect --split test --resume`, `evaluate --stage test --locked`, appropriate tests.

**Stop:** NO_GO for substantive failure; INCONCLUSIVE for promising but unresolved intervals or mechanism. No more test episodes, favorable seed, penalty change, or class exclusions. Proceed to M6 unless GO.

### M5 — actual execution and stress (requires M4 GO)

**Files:** Extend live/stress/challenge entry points in `pipeline.py`, CLI, and reporting; fresh public/private task and panel manifests; integration/cache/source-shift tests; `reports/m5.md`.

**Work packages:**

1. Freeze the entire panel manifest and measured two-hour forecast before calls: 16 fresh episodes from at least four fresh roots, two-file tasks including the reserved transfer class; randomized policy execution order; 16 fixed-ID source-shift proposals and intervention assignment; 16 eager-grounded alternatives; second-seed subset of eight and exact requested fresh-check protocol. No fitting on panel labels.
2. **Panel A:** generate one frozen proposal per fresh episode; independently execute only checks P/champion request, no research-cache shortcut. Apply into separate disposable copies; grade after both decisions. Count real loading/warm overhead and replay each actual acquired trajectory afterward.
3. **Panel B:** preserve proposal code/labels, change copied lineage, missing metadata, contradictory/outdated docs, or D availability and rerun only affected checks. Expose observable provenance/availability only. Separately perform CPU-only within-(Y,lineage) R2 recombination; mark strata with fewer than two observations unavailable. Neither controlled result joins the natural estimate.
4. **Panel C:** run eager actor+T on its own 16 proposals and rerun the fixed eight-episode subset with a second actor seed/fresh review calls. Report raw quality, costs, and instability; no second high-powered significance claim.
5. Reconcile actual versus replay directions, overhead, copied-source confidence, cache/calibration invalidation, both terminal file behaviors, nondeterministic verdicts versus broken replay, source-shift/fresh-task/seed quality, and whether eager grounding removes practical value.

**Required tests/evidence:** no hidden files, stale PASS or duplicate apply; model/source/prompt/environment identity changes cannot reuse applicable evidence; changed model/check versions require fresh calibration rather than online fit; exact acquired histories reproduce decisions; nondeterminism is separately recorded; stage forecast includes all panel calls/repeats. Commands: `live --panel fresh`, `stress --panel sources`, `challenge --panel eager-grounding`, integration tests.

**Stop:** BLOCKED execution for safety/leakage/protocol defects; NO_GO for substantiated simpler-workflow/effect failure; INCONCLUSIVE for unresolved small-panel reversal/instability. No larger machine or extra panels.

### M6 — report and artifact freeze (reachable after any stop; no model calls)

**Files:** `reports/final.md`, report tables/traces, artifact manifest, README reproducibility section, finalized existing lock/config/versions and CLI report code/tests.

**Work packages:**

1. Generate one overall scientific status, plus optional BLOCKED execution, from executed gates. Check that unexecuted stages remain explicitly unexecuted and no missing evidence can imply a pass. Preserve every failed/revised pilot/mechanism record.
2. Write a short report with the full baseline table where reached, A/B/C separately, uncertainty/observed guardrails and risk limitations, fixed-rule examples, failures, controlled-versus-natural distinction, costs/break-even, exact machine/model/task scope, and links to raw artifacts. If blocked before LLM work, report setup-only INCONCLUSIVE, not negative scientific evidence.
3. Verify hashes, immutable records, denominators, complete budgets, actual version/image/model pins where reached, exact reproducibility commands, and reachable preserved artifacts. Run existing ordinary tests and `report`; no new model calls or future-stage scaffolding to fill empty sections.

**Completion:** LOCAL_POC_PASS only after M4 efficiency/mechanism and M5 survival; NO_GO preserves any positive adaptive/generic finding; INCONCLUSIVE names the unresolved quantity. Any next study requires a new question/design, not a silent continuation of this locked experiment.

## Plan coverage and execution handoff

| Specification concern | M0 tasks | Later owner |
| --- | --- | --- |
| Identity, immutable records, schema/status errors | 1, 5, 7 | M1/M2 real metadata |
| Public/private separation and disposable mutations | 2, 5, 6, 8 | M1 real evaluator/runner, M5 live |
| Exact tables/planning and copied/complementary controls | 3, 4 | M3 fitted models |
| Masked replay and original-cost accounting | 6, 8 | M2 collection, M4 locked replay |
| Gate/budget/resume boundaries | 7–9 | Every collection stage |
| Benchmark contracts, mutants, natural roots | 2 fake checks only | M1 pilot, M3 expansion |
| Full baseline parity, smoothing, champion selection | 4 initial policies only | M2 screening, M3 complete ladder |
| Statistics, calibration diagnostics, economic sensitivity | 8 arithmetic only | M3/M4 |
| Hardware/model/container envelope | Explicitly excluded | M1 |
| Live/grounding/source/seed panels | Explicitly excluded | M2 grounding, M5 complete panels |
| Reporting after early failure | 8, 9 | M6 from any stage |

The plan's self-review checks interfaces and ownership against the spec, test coverage for the five review-focus cases, exact thresholds, two locks, and the absence of invented measurements. Test snippets are intended future assertions; none is a claim that code or tests exist now.

Recommended future execution is native, milestone by milestone: the small modules share interfaces, inference is intentionally serial, and independent model workers would violate the experimental envelope. Native execution may still use whatever review workflow is explicitly selected later; this planning task does not dispatch agents or start implementation. The next concrete action, when implementation is requested, is Task 1 of M0.
