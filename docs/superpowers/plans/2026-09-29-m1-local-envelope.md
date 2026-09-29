# M1 local execution envelope implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax. The user authorized continued native execution on the current branch and meaningful commits.

**Goal:** Replace the blanket disk rule, establish the actual Mac/model/container envelope, and advance only after M1 GO.

**Architecture:** Trusted host code stages only public candidate files, compares private outputs outside a bounded container, and owns a single restartable native MLX worker. Small JSON manifests hold resource estimates, immutable revisions, smoke inputs, measurements, and gates. Existing M0 records, preflight, parser, and budget accounting remain the shared boundaries.

**Tech Stack:** Existing Python 3.12 environment, standard library, NumPy/SciPy/pytest; lazily imported MLX LM; installed Docker Desktop and a digest-pinned Linux ARM64 Python image.

**Spec:** [Project specification](../specs/2026-09-29-dependency-aware-verification-design.md), with the user-authorized storage amendment on 29 September 2026.

## Global constraints

- Preserve M0's completed work and current `main`; no new worktree or remote push.
- Replace the 20 GiB blanket target with per-filesystem incremental needs: aggregate uncached downloads, dependencies, image/staging/record growth; require 1.5 times that total plus 1 GiB free headroom per affected filesystem. Count a complete verified cached asset once, not again as a download. Check Docker VM free space separately.
- One resident model and one request; input 3,072, proposal output 512, review output 128, total context 4,096 tokens. Exact chat-template counting; no truncation or format repair.
- Model timeout 180 seconds; M1 model-active budget 900 seconds and total budget 43,200 seconds. Startup, warm-up, retries, and failures count. Full timeout reservations precede work.
- Candidate: Linux ARM64, no network, read-only, no privileges/capabilities, UID/GID 65534, 1 CPU, 512 MiB memory with equal swap limit, 32 processes, 64 MiB restricted tmpfs. Ten-second outer watchdog; combined stdout/stderr 65,536-byte cap; tracked forced removal.
- Native MLX only; immutable model/tokenizer revisions, safetensors weights, remote code disabled. No host execution fallback, fine-tuning, repair loop, calibration fitting, or benchmark expansion beyond 24 pilot tasks.
- Leave `max(8 GiB, .25 × RAM)` outside planned work. Freeze memory-pressure/swap sampling before inference. A resource failure remains BLOCKED; it does not become a negative scientific result.
- Reviews see only their fixed packet/contract/proposal. Hidden reference code, hidden expected outputs, and hidden test source never enter prompts or containers.

## Review focus

1. Cache and workspace on different volumes must not be double counted or subjected to a blanket workspace minimum — Task 1.
2. CLI interruption/output flooding must remove the actual container, including when its ID has not yet returned — Task 2.
3. Private reference/expected-output canaries must never appear in staged files or candidate inputs — Tasks 2 and 3.
4. Worker timeout/crash must retain costs and terminate the resident model before restart; token overflow must make no generation call — Task 4.
5. A warm measurement must include startup and all planned pilot/eager calls in its 1.5× forecast, without using unknown test outcomes — Task 5.

### Task 1: amend storage and implement local resource diagnostics

**Files:** Modify spec, original roadmap, `config.toml`, `pipeline.py`, CLI, README/reports; create `resources.py`, `tests/test_resources.py`.

**Interfaces:** `storage_plan(items: list[dict], *, margin: float=1.5, reserve_bytes: int=1073741824) -> dict` groups path/free/extra-byte entries by device and refuses insufficient or unknown needs. `doctor_local(run_dir: Path, config_path: Path) -> dict` runs bounded read-only probes, records actual paths/free space, hardware/power/engine availability, and a preliminary resource status. No model or candidate execution.

- [ ] Write failing cases for separate volumes, shared-volume aggregation, cached downloads, insufficient space, and invalid estimates; config must accept the amended storage section and retain every inference/research cap.
- [ ] Run `.venv/bin/python -m pytest tests/test_resources.py -q`; expect missing storage API/config behavior.
- [ ] Implement the minimal storage schema and resource probes. Replace old active documentation; preserve historical gates/manifests and mark the old workspace-only stop superseded. A preliminary doctor never certifies M1 GO.
- [ ] Run targeted and full pytest, `doctor --local`, and whitespace checks; inspect actual results.
- [ ] Commit `fix: budget storage on the filesystems that hold the assets`.

### Task 2: implement and exercise the isolated runner

**Files:** Extend `runner.py`; create `tests/test_runner.py`, a fixed driver under `src/depverify/`, and isolated-runner fixtures.

**Interfaces:** `ContainerRunner(image: str, *, engine: str='docker', timeout: float=10., output_limit: int=65536).run(files: dict[str,str], entry_point: str, inputs: list) -> dict` stages only supplied public files plus its fixed driver. `runner_environment(image) -> dict` resolves/records the installed engine and pinned image identity. Result includes status, returned outputs, wall time, exit code, bounded raw output, cleanup state, and staged-file hashes.

- [ ] Write failing tests for ordinary JSON behavior, exact staging, image digest requirement, no hidden expected outputs, and refusal when the engine is absent. External engine fixtures are opt-in; ordinary tests do not pull images.
- [ ] Run targeted tests and observe missing runner behavior. Implement fresh staging, argument-list execution, nonblocking bounded streams, fixed container identity, deadline/removal, and explicit candidate/infrastructure statuses.
- [ ] Resolve/pull one ARM64 Python image, record its digest, then run ordinary and hostile fixtures: loop, flood, forks/subprocesses, network, home read, protected write. Assert denial/termination and successful cleanup. No host fallback.
- [ ] Run full ordinary pytest and commit `feat: run candidate code in a bounded disposable container`.

### Task 3: create and validate only the pilot benchmark

**Files:** Extend `tasks.py`; create public pilot JSONL/manifests, private references/cases, `grading.py`, `tests/test_evaluator.py`.

**Interfaces:** `load_pilot() -> list[Task]` loads exactly six roots with four semantic contract variants each. `grade(task: Task, proposal: Proposal, runner: ContainerRunner) -> dict` loads private expected behavior on the host and sends only public code and input values to the runner. `validate_pilot(runner) -> dict` checks references, original bugs, boundary/constant/example mutants, and independent invariants/enumeration.

- [ ] Write failing loader and isolation tests; ensure private canaries stay host-side, malformed proposals remain failures, and root groups are disjoint/real.
- [ ] Run targeted tests. Define public contracts first, then straightforward references and differently formulated checks. Natural generations are not created in validation.
- [ ] Run all references and mutants through the container, report every task's admission result, and block on contradictions/unresolved evaluator errors.
- [ ] Run full ordinary pytest and commit `feat: add validated pilot contracts and private grading`.

### Task 4: add a serial native model worker and fixed prompts

**Files:** Create `local_model.py`, four prompt files, `tests/test_local_model.py`; extend `checks.py`, lock/environment manifests.

**Interfaces:** `LocalModel(model_path: Path, identity: dict, ledger: Path, limits: dict, stage: str).start()`, `.generate(messages: list[dict], *, role: str, seed: int, temperature: float) -> dict`, `.close()` own one process and JSON-only IPC. A fake transport tests timeout and token boundaries without MLX. `assemble_messages(task, role, proposal=None) -> list[dict]` uses explicit allowed inputs only.

- [ ] Write failing token-cap, serial-worker, restart/timeout, retained-cost, and prompt-isolation tests. No MLX import in fake tests.
- [ ] Run targeted tests. Install MLX LM, inspect the actual working API, resolve full immutable conversion/upstream identities and exact asset sizes, and download one default model to its existing cache. Record the actual package versions; no invented pins.
- [ ] Implement lazy local loading with remote code disabled, exact chat-template input counting, seeded generation, strict caps, stream timing/token/peak-memory records, and outer worker kill/restart. Reserve/debit all actual work using the existing ledger.
- [ ] Run full ordinary pytest and commit `feat: add bounded serial MLX proposal and review calls`.

### Task 5: freeze smoke inputs, measure, and record the M1 gate

**Files:** Extend `pipeline.py`, CLI, tests, README, `reports/m1.md`, frozen smoke and environment/measurement artifacts.

**Interfaces:** `smoke_local(run_dir: Path, config_path: Path) -> dict` requires current M0 evidence, local prerequisites, admitted pilot tasks, and isolation checks. It freezes task IDs/seeds/calls before generation and returns criteria/measurements/forecast. `forecast_stage(measurements: dict, counts: dict, *, margin: float=1.5) -> dict` estimates startup, capped prompt/output work, execution, and all additional eager calls. Gate GO only with ordinary/isolation success, ≥90% valid smoke review JSON, bounded termination/memory, and feasible M2 forecast.

- [ ] Write failing budget/startup-inclusive forecast and CLI gate tests. Test source/label isolation and no automatic M2 launch.
- [ ] Implement a fixed small warm-up/proposal/review/repeat schedule within 900 model-active seconds. Sample memory pressure every second; freeze critical/warning and sustained-swap rules before calls. Persist every attempt and separate changed text from changed verdicts.
- [ ] Re-verify M0 against current code/config; run `doctor --local`, isolated pilot admission, frozen smoke, pytest, and whitespace checks. Inspect costs, outputs, pressure, and forecast before writing M1 GO/BLOCKED/INCONCLUSIVE.
- [ ] Commit observed results and request one fresh read-only review of this M1 range. Fix Important/Critical findings once with RED→GREEN plus the whole suite; preserve minors/rulings. Only after M1 GO refine the M2 plan and collect its 24 natural episodes.

## Self-review and execution handoff

The interfaces match existing `Task`/`Proposal` records, strict review parsing, and model/execution reservations. Hidden grading remains an explicit host-side module; real input/output and cleanup fixtures prove isolation. The new storage rule is the user's authorized amendment, not a research-threshold revision. All other budgets, model fallbacks, gates, and sample sizes remain unchanged. Native execution and current-branch commits are already authorized; continue without another handoff question.
