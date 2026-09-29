# Dependency-aware verification: project specification

**Date:** 29 September 2026

**Status:** M0 implemented; M1 execution continues under the user-authorized storage amendment of 29 September 2026.

**Authority:** The project brief supplied with this request. Its budgets, sample sizes, gates, and exclusions remain binding.

**Companion:** [M0 implementation plan and gated roadmap](../plans/2026-09-29-dependency-aware-verification.md).

## 1. Purpose and scope

Build a small local research instrument that proposes a single-file Python change, chooses which verification evidence to acquire, and either installs the frozen file in a disposable repository or defers. Test whether modeling the shared provenance of two reviews improves decisions and total cost on unseen tasks. The deliverables are a tested implementation, reproducible local benchmark, and an honest final decision, including a useful negative result.

The intended operator is the researcher on one M3 Max MacBook. RAM, macOS, available storage, installed Python, container engine, and inference performance are measurements to make, not facts assumed by this specification. No Mac inspection, model run, container isolation test, or benchmark result is implied by this document.

Report three distinct claims:

| Claim | Evidence required |
| --- | --- |
| A: adaptive verification helps | Improvement over always accept/defer, test-only, single checks, and fixed sequences |
| B: dependence matters | Useful held-out difference from independence, plus controls that change coupling without changing marginal accuracy |
| C: this structure is worthwhile | Useful advantage over source deduplication, full joint acquisition, and generic learned-pair acquisition |

A positive A with a failed B or C is a useful baseline result, not validation of the proposed special mechanism. This is application-level evidence acquisition, not new neuroscience, a novel foundation for active acquisition, universal semantic verification, or production safety validation.

There is no primary repair loop, best-of-N proposal selection, model training, fine-tuning, online learning, extra compute purchase, service, database, agent framework, dashboard, or production deployment. Preserve the proposed patch across policies. Do not rescue a failing gate by changing thresholds, inflating test costs, withholding useful evidence, or making tasks harder.

## 2. Chosen approach and alternatives

Use a serial Python CLI, immutable JSON/JSONL records, a coherent finite probability table, and exact CPU planning. Collect each available check once for a frozen proposal; replay policies using an accessor that reveals only requested verdicts. This is small enough to test exhaustively and makes the natural-workload comparison paired.

Two alternatives are relevant but unsuitable as the primary architecture:

1. A live-only evaluation is closer to deployment immediately, but repeated inference confounds policy comparisons and consumes the budget. Keep live execution as M5 validation.
2. A notebook containing full evidence tables is quick to prototype, but makes future-outcome and label leakage easy. Keep analysis in `evaluate.py` and make the policy interface incapable of receiving those tables.

The project is one bounded research system with milestone-dependent additions. Only M0 receives a detailed executable task plan now. Later milestones have a roadmap; refine their next task plan from measurements after the predecessor gate passes. Documentation of a later stage does not authorize its collection or scaffolding.

## 3. Milestone state machine

Each milestone writes one short `GateResult` JSON record and explanatory report lines. Gate statuses are `GO`, `NO_GO`, `BLOCKED`, and `INCONCLUSIVE`. An absent record means unexecuted, never GO. Each record binds its inputs, code/config hashes, check results, measurements, reasons, and evidence paths. A relevant artifact change makes an old GO stale. Keep superseded records instead of overwriting history.

`BLOCKED` denotes a mathematical, implementation, evaluator, or environment defect. Repair it before advancing; it is not negative evidence about the hypothesis. `NO_GO` stops this mechanism and proceeds to reporting. `INCONCLUSIVE` stops expansion unless the specifically permitted bounded revision applies. A budget stop checkpoints incomplete work and is not an implicit exclusion of remaining episodes.

| Stage | Work permitted | GO criterion / terminal disposition |
| --- | --- | --- |
| M0 | Records, fake checks/runner, known tables, exact planner, accounting, isolation tests | Mathematical, masking, permission, accounting, termination, and positive/negative controls pass; otherwise BLOCKED |
| M1 | Pilot task materials, one model setting, isolated runner, small smoke panel | Ordinary smoke and hostile fixtures pass; at least 90% of smoke reviews parse; no leak/truncation/swapping issue; projected M2 fits; otherwise BLOCKED |
| M2 | 24 natural pilot episodes plus eight eager-grounded episodes | Every pilot screening condition in §14 passes; otherwise NO_GO or INCONCLUSIVE |
| M3 | Extend/lock benchmark; 96 train + 48 development episodes; fit/tune policies | Every development condition in §14 passes; otherwise NO_GO or INCONCLUSIVE |
| M4 | Freeze run, then 128 locked episodes and CPU replay | Efficiency, quality, support, and adjusted mechanism comparisons in §14 pass |
| M5 | Small live, source-shift, grounding, and seed panels | Actual sequential integration preserves savings and reveals no material contradiction |
| M6 | Report and artifact freeze; no additional model calls | Exactly one scientific status: LOCAL_POC_PASS, NO_GO, or INCONCLUSIVE |

M6/reporting is reachable after any stop. Setup-only failure has scientific status `INCONCLUSIVE` with execution status `BLOCKED`; it must not be relabeled a negative benchmark. At most one fresh 24-episode replacement pilot is allowed for a documented defect or obvious difficulty mismatch. At most one substantive mechanism revision is allowed before M4. Neither resets a budget. No outcome-dependent test expansion is permitted.

## 4. Repository and responsibility boundaries

Create a file only when its milestone needs it. Avoid abstract plugin layers. Use the standard library, NumPy, SciPy, and pytest; add `mlx-lm` at M1 and import it lazily. Use Python 3.11 or another installed version supported by the dependencies actually pinned. Store tables as JSON or NPZ, with pickle loading disabled.

| File or directory | Responsibility | First needed |
| --- | --- | --- |
| `README.md`, `pyproject.toml`, `requirements.lock`, `config.toml`, `.gitignore` | Setup, verified pins, limits, commands, generated-data exclusions | M0 |
| `src/depverify/__init__.py`, `__main__.py` | Package and argparse CLI; delegate domain logic | M0 |
| `records.py` | Five dataclasses, validation, canonical hashes, atomic records/JSONL | M0 |
| `tasks.py` | Public task loading, protected-file manifests, preflight, disposable copies, split validation | M0, extended M1/M3 |
| `probability.py` | Validated coherent distributions and marginal queries; later count fitting | M0, fitting M3 |
| `policy.py` | Exact DP, terminal decisions, fixed policies; no private data/file loading | M0, baselines M2/M3 |
| `checks.py` | Four fixed adapters, strict verdict parsing, fake checks | M0, real checks M1 |
| `runner.py` | Fake execution first; bounded container execution later | M0, container M1 |
| `evaluate.py` | Trusted replay accessor, post-decision label join, metrics and grouped inference | M0, inference M3/M4 |
| `pipeline.py` | Orchestration, gates, reservations/ledger, immutable collection and live application | M0, collection M2 |
| `local_model.py` | One serialized restartable MLX worker and fake model adapter | M1 |
| `bench/public/`, `prompts/` | Allowed contracts, code, examples, source manifests, prompt versions | M1 |
| `bench/private/` | References, hidden inputs, labeler definitions; never evaluated-agent inputs | M1 |
| `tests/` | Mathematical, protocol, replay, file boundary, runner, and integration checks | M0 onward |
| `runs/` | Generated records, raw outputs, ledgers, locks, parameters; Git ignored | M0 onward |
| `reports/` | Gate summaries and final readable report, linking preserved run artifacts | M0 onward |

The repository author may read private benchmark materials. The evaluated model only receives explicit prompt inputs; the candidate container only receives staged allowlisted files and input values. Python module boundaries prevent accidental policy leakage, not malicious researcher introspection. The container is the code-execution boundary; prompt text or an AST filter cannot replace it.

The data path is: public task → one proposal → shared preflight → frozen proposal → fixed-input checks → masked policy history → ACCEPT/DEFER → disposable apply/defer → trusted grading and analysis. Full evidence and private labels remain on the trusted side. Labels join trajectories only after decisions.

## 5. Records, identity, and error semantics

Use one dataclass each for `Task`, `Proposal`, `CheckResult`, `Decision`, and `GateResult`. Prefer frozen records and tuples for immutable fields. Ancillary ledgers/manifests are validated JSON dictionaries, not an expanding hierarchy of domain objects.

| Record | Required content |
| --- | --- |
| `Task` | Schema version, episode/root IDs, split/class, issue/contract, single editable relative path, expected entry point, base/public support hashes, public tests, source manifests; no hidden cases/reference/label |
| `Proposal` | Episode ID, exact replacement bytes/hash, proposal key, status, actor revision/seed/config/prompt hash, tokens, elapsed time, preflight time, environment/check/source identities |
| `CheckResult` | Proposal key, check ID/version/seed, source and prompt hashes, model/tokenizer identities, verdict/status, retained reason/raw-output hash, input/output tokens, elapsed seconds, timeout/cache flags, attempt IDs |
| `Decision` | Proposal key, policy artifact hash, acquired ordered `(check_id, verdict)` history, terminal action/status, controller/wrapper time, selected charged cost; no label or unrequested outcome |
| `GateResult` | Stage, status, timestamp, artifact hashes, named criteria and values, reasons, evidence paths, budget snapshot |

Every episode/check record includes or references its `root_group_id`, split, task class, source versions/lineage, machine-profile hash, and environment hash. These analysis fields do not automatically become controller features. Label JSONL is separate, keyed by episode ID; controlled-condition/provenance truth is a separate private artifact.

Canonical hashing uses UTF-8 canonical JSON for structured fields (`sort_keys`, fixed separators, finite numbers only), plus named raw-file hashes. Do not concatenate ambiguous strings or normalize candidate/source bytes before hashing. The frozen proposal key binds `task_contract`, `base_repository`, `replacement_file`, `environment_version`, `check_versions`, and `allowed_source_manifest` with SHA256. Cache identity additionally binds check ID/version, exact assembled prompt bytes, model/tokenizer revisions, sampling settings/seed, and relevant source hashes.

Write records atomically, retain immutable attempts, and use stable event IDs. Resume validates hashes and reuses only complete matching records. Interrupted writes cannot become complete evidence. A trailing incomplete JSONL event is preserved as interrupted evidence before repair; conflicting duplicate IDs are BLOCKED. Unknown in-flight work cannot be assumed free: reconcile it or conservatively charge its reservation. There is at most one infrastructure retry with identical input/seed, retaining both attempt costs. Never retry an unfavorable valid verdict, bad patch, public failure, or format failure.

Verdicts are exactly `PASS`, `FAIL`, `UNKNOWN`. `NOT_ACQUIRED` is history state, not a verdict. Terminal decisions are exactly `ACCEPT`, `DEFER`. Separate execution status from verdict: examples include `ok`, `format_error`, `truncated`, `input_over_budget`, `unavailable`, `model_timeout`, `candidate_timeout`, `output_limit`, `infrastructure_error`, `invalid_proposal`, `zero_support`, and `calibration_invalid`.

Private labels are `Y=1` for passing the specified evaluator, `Y=0` for a genuine candidate failure/invalid proposal/reproducible candidate timeout, and `LABEL_UNRESOLVED` for evaluator/environment failures. UNKNOWN is never silently converted to PASS or to a correctness label. More than 2% unresolved episodes blocks the stage. Any remaining unresolved cases require policy-blind handling and denominator disclosure, never favorable scoring.

## 6. Task and proposal contract

Use self-contained Python micro-repositories, usually one editable file plus one or two immutable support files, with JSON-compatible inputs/outputs. Candidate task classes include boundaries, transformations, stable ordering, precedence, parsers, pagination/chunking, and explicitly versioned local API migrations. Exclude network/service dependencies and OS-dependent or consequential real-world tasks.

The actor sees the explicit contract, original code, public tests/examples, immutable public support, and initial source packet A. It returns the entire replacement file as raw UTF-8 Python, not arbitrary patch instructions. An implementation choice fixed here is a 64 KiB replacement-byte cap, alongside the stricter 512-token generation cap. No wrapper or LLM repairs malformed output.

Shared preflight validates the exact allowlisted relative path, one replacement file, size, syntax via parsing only, unchanged protected hashes, and the expected entry point. Reject absolute/traversal paths and symlink escapes. Never import or execute candidate code on the host. Invalid or out-of-scope proposals incur their costs, receive DEFER under every policy, and remain in the natural denominator.

Only the disposable candidate copy may change. Immediately before acceptance, recheck the proposal/environment/source identities and protected manifest. Atomic installation is idempotent for the same proposal key; conflicting content or stale evidence causes refusal/DEFER. Deferral leaves the disposable base unchanged. Never change the research checkout, other projects, permissions, network settings, or tests.

Define a contract before writing its reference. Admit a task only if: the reference passes public and hidden checks; the original bug fails a contract-derived case; boundary/constant/public-example-special-case mutants are rejected where applicable; and allowed variants remain unambiguous. Include a differently formulated independent check, such as exhaustive small-domain enumeration or invariants. Mutation fixtures are evaluator validation, never natural proposals.

| Split | Roots | Variants per root | Episodes | Use |
| --- | ---: | ---: | ---: | --- |
| Pilot | 6 | 4 | 24 | Debug/screen only; excluded from final claims |
| Train | 24 | 4 | 96 | Fit likelihoods, action costs, and training-only structure selection |
| Development | 12 | 4 | 48 | Select the declared configurations and champion |
| Locked test | 32 | 4 | 128 | One final natural comparison |
| Total | 74 | 4 | 296 | Incremental creation/collection |

One underlying program/bug template and all source alterations, variants, seeds, and repeats are one root group. Merge related groups conservatively. Constants or renaming never create independent roots. If credible independence cannot support these targets, report a smaller exploratory/inconclusive study without fabricating effective sample size. Include multiple classes per split and reserve at least one class for the separately labeled M5 transfer panel. Task class/ID is not a policy feature.

Build only pilot materials before M2. After M2 GO, validate and hash all train/development/test contracts, references, sources, and splits before M3 fitting or collection. Do not generate or inspect test model outcomes at this first lock. A second lock, `frozen_run.json`, freezes fitted settings before M4 test proposal generation.

## 7. Evidence menu and provenance

| ID | Fixed input beyond proposal and contract | Cost |
| --- | --- | --- |
| R1 | Initial packet A, first review prompt | Local inference and adapter overhead |
| R2 | Packet B, fixed alternative review prompt | Local inference and adapter overhead |
| T | Exactly the public tests already available to the actor | Fresh isolated execution and overhead |
| D | Pinned target-version documentation/local API-contract packet | Lookup/preparation plus inference and overhead |

R1, R2, and D use the same resident model serially, reset conversation state per call, and initially share no cross-check KV cache. R2's source relationship to A is `same_lineage`, `distinct_lineage`, or `unknown_lineage`, derived only from public source manifests/content hashes. Different names/URLs/paraphrases do not establish distinct provenance. Known same-origin derivatives remain shared. Distinct provenance is not statistical independence; D can share model errors with either reviewer.

Only cheap provenance/version/availability metadata is initially available to the controller. Source bodies cost their check to acquire. A review sees no previous outcomes/reviews, actor reasoning, policy identity, private tests, hidden labels, or injected-condition name. Reasons are inspection artifacts, not controller features or inputs to a second judge. Treat instructions embedded in source text, code, or test inputs as data, with no new capabilities.

The review output is exactly an object with `verdict` and a string `reason`, for example `{"verdict":"PASS","reason":"The boundary agrees with the supplied contract."}`. Strict parsing rejects extra prose, duplicate keys, unsupported verdicts/types, non-finite JSON, truncation, and refusal. Record UNKNOWN and incurred costs; do not scrape a favorable verdict out of malformed text or repair it with a model.

Token-count the final chat-template prompt before every call. Over-cap actor input causes a retained deferred proposal; over-cap review input causes UNKNOWN. Never silently truncate a contract. Prompt versions and exact bytes are hashed.

T=FAIL means a reproducible counterexample to a valid public requirement. It is an acceptance veto once acquired, shared by every policy. Engine/evaluator failure is UNKNOWN. A reproducible candidate timeout/failure may constitute a public counterexample; diagnose its candidate origin before marking FAIL. Unrequested T=FAIL is not visible to the policy. Public PASS is partial evidence only.

## 8. Local model and execution envelope

Use native macOS MLX inference, supported by the [MLX LM documentation](https://github.com/ml-explore/mlx-lm). Default model: `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit`; resource/setup fallback: `mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit`. Record both the [conversion](https://huggingface.co/mlx-community/Qwen2.5-Coder-7B-Instruct-4bit) and [upstream](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct) identities, and equivalent identities if using the [fallback](https://huggingface.co/mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit). A fallback is a different model setting, chosen before calibration and logged with its reason.

At M1 resolve immutable model/tokenizer revisions, download safetensors only for weights, and enforce `trust_remote_code=False`. Use the supported local-path loading API of the version actually installed; do not invent arguments or pins. Record successful package versions in `requirements.lock`, revisions and ARM64 image digest in the environment manifest. Do not follow `main` during collection. Model/check version changes invalidate calibration as well as applicable caches.

| Limit | Value |
| --- | ---: |
| Resident LLMs / concurrent model calls | 1 / 1 |
| Input tokens, including chat template | 3,072 |
| Proposal / review output tokens | 512 / 128 |
| Maximum total context | 4,096 |
| Acquisitions per proposal | 4, each check at most once |
| Model call wall time | 180 seconds; kill/restart worker on timeout |
| Candidate container | 1 CPU, 512 MiB, 32 processes |
| Candidate invocation wall time | 10 seconds with outer watchdog |
| Candidate combined stdout/stderr | 64 KiB; terminate at cap |
| Storage before downloads/stages | Per-filesystem additional bytes × 1.5, plus 1 GiB free headroom; verify actual asset and Docker VM needs |
| M1 / M2 model-active budgets | 15 / 60 minutes |
| M3 / M4 / M5 model-active budgets | 4 / 3 / 2 hours |
| Total model-active budget | 12 hours, including failed/repeated calls |

Storage amendment (29 September 2026, explicitly requested by the user): there is no blanket 20 GiB repository-volume minimum. Locate the model cache, dependency environment, Docker disk, staging, and records. Sum incremental uncached asset sizes on each filesystem, include download/image overhead, and require 1.5× that sum plus 1 GiB headroom there. Complete verified cached assets do not require another download copy. Resolve exact model sizes before download and verify Docker VM free space separately. Unknown or insufficient needs block the relevant operation; a small repository volume does not block downloads to another adequately provisioned volume.

Detect RAM using `sysctl -n hw.memsize`, architecture with `uname -m`, and macOS with `sw_vers`. Record AC status/power mode, observe memory pressure and swap changes, and warm up before timing. Planned experiment working set must leave `max(8 GiB, 25% of physical RAM)` outside it, including allowance for the container engine. Sustained swap growth or serious pressure blocks expansion; never raise privileged memory limits. M1 fixes and records the sampling cadence/rule used to judge sustained pressure before M2.

A single restartable model worker owns MLX; an outer host watchdog can terminate it. Loading/restarting and inference work count, idle residency does not masquerade as generation time. Record cold loading separately from warm prompt processing/generation and measure actual adapter/container overhead. Freeze actor temperature 0.2 and reviewer temperature 0 initially; fixed independent seeds improve repeatability without claiming bitwise determinism.

Use one installed Docker-compatible engine for CPU execution, an ARM64 Python image pinned by digest, and these exact controls, supported by the [Docker run reference](https://docs.docker.com/reference/cli/docker/container/run/):

```text
--platform linux/arm64
--network none
--read-only
--cap-drop ALL
--security-opt no-new-privileges=true
--user 65534:65534
--cpus 1
--memory 512m
--memory-swap 512m
--pids-limit 32
--tmpfs /tmp:rw,noexec,nosuid,size=64m
```

Stage only allowlisted candidate/public files and a fixed runner; mount read-only. Pass JSON input values through the controlled input channel. Do not mount hidden test source, expected outputs, reference code, home, credentials, research checkout, or engine socket. Trusted host code computes/loads expected behavior and compares returned JSON outside the container. Public verification and private grading use separate fresh invocations.

Use argument vectors, never model-text shell interpolation. Track container ID and a unique run-owned name/label before launch; force removal on timeout/output flood/cancellation, including a CLI failure before a cidfile appears. Drain bounded output without deadlock and prevent engine-side logs from growing without bound. Failure to confirm cleanup blocks subsequent execution. Killing only the CLI is insufficient. Keep default security restrictions; no host execution fallback. Docker's [security documentation](https://docs.docker.com/engine/security/) describes isolation mechanisms and limitations; this setup is not a hostile multi-tenant certification.

Before smoke GO, test infinite loops, output floods, subprocess spawning, network access, home-file reads, and protected-file writes. Use synthetic canaries, not real credentials. Verify denial/termination and absence of leaked host/private data.

## 9. Collection, replay, and accounting

For each mechanically valid proposal, collect every available check once, using a balanced seeded order, a fresh execution environment, and fixed check-specific seeds independent of decisions/labels. Keep all natural proposals, including invalid ones. Seeds, balancing schedule, eager-grounding subset, manual trace IDs, repeat-call subset, and timing-repeat rules are frozen before relevant outcomes exist.

The primary benchmark provisions all four sources/checks. Known unavailable actions have no acquired verdict and are masked from planning; attempted but failing actions can yield UNKNOWN with cost. For fitting fully observed tables, use the same complete, mechanically valid, resolved training subset for I/P/J/learned-pair; do not impute missing acquisitions as observed UNKNOWN. Disclose support exclusions separately; those episodes remain in workflow evaluation. No label balancing or favorable resampling is allowed.

The trusted accessor owns full check records. The policy only receives lineage, action-availability mask, training-estimated costs, and an acquired-verdict history. `request(check_id)` reveals only that verdict and charges the original measured action duration to a trusted ledger. The policy never receives actual completion times as predictors, raw reasons, full records, task IDs, or label handles. Duplicate/unavailable requests fail before a second charge or side effect. A genuine R2 action is charged even if its text equals R1.

Replay cost is original measured work, never JSON/cache lookup latency. Charge shared actor/preflight costs to every policy; time controller and application/defer wrappers under the declared execution convention. Keep actual research collection work, including unselected checks and grading, in a separate ledger. A cache hit in live deployment has its own declared regime and cannot be compared silently with an uncached baseline.

Replay is valid because check inputs do not depend on previous outcomes. If any check starts consuming the current transcript or state persists across checks, stop and redesign instead of reusing these tables.

Before each stage, estimate remaining prompt processing, generation, startup, overhead, and timeout/retry work from measurements, multiplied by 1.5. Refuse a stage whose projected work exceeds its stage or total allowance. The 296-episode core has an output-token ceiling of `296 × (512 + 3 × 128) = 265,216`; smoke, eager grounding, one possible replacement pilot, repeated calls, and M5 are additional. This is not a runtime forecast.

Before each call reserve its timeout allowance, then debit actual work and release the remainder. Model and execution work have separate ledger dimensions: container time contributes latency/research work, not model-active time. Stage exhaustion stops/checkpoints the whole stage with intended denominators intact. A common per-proposal action cap can instead force DEFER; it never authorizes stage overrun. If several measured cases run over 1.5 times the estimate, checkpoint and re-estimate under the frozen timing rule. Sleep/thermal/unrelated-job interruptions are tagged; repeats follow a policy-blind rule and retain all research costs.

## 10. Probability models and exact planning

Use ordered checks `(R1, R2, T, D)`, verdicts `(PASS, FAIL, UNKNOWN)`, and lineage groups `(same_lineage, distinct_lineage, unknown_lineage)`. Each group has a joint array of shape `(2, 3, 3, 3, 3)` containing `P(Y, outcomes | g)`. History has four entries in `{NOT_ACQUIRED, PASS, FAIL, UNKNOWN}`; availability is a separate four-bit mask.

The three models share helpers, fitting rows, priors, costs, feature access, and exact planning:

```text
I: P(Y) × ∏j P(oj | Y,g)
P: P(Y) × P(oR1,oR2 | Y,g) × P(oT | Y,g) × P(oD | Y,g)
J: P(Y) × P(oR1,oR2,oT,oD | Y,g)
```

Estimate `P(Y)` with Beta(1,1); it is not a lineage-conditioned shortcut. Use symmetric pooled singleton pseudocounts, shrink group singletons to pooled distributions, shrink the pooled pair to the product of pooled singletons and group pairs to the pooled pair, and shrink the pooled joint to the pooled independent product and group joints to the pooled joint. For every block use `(count + alpha × backoff_probability)/(support + alpha)`. For pooled singletons the symmetric backoff is uniform. Select one alpha from `{4, 16, 64}` independently per model with equal three-configuration budgets on development objective.

Preserve structural zero mass for `Y=1,T=FAIL`; enforce and renormalize consistent conditional supports in every model/backoff. A contradictory training row is a benchmark defect, not smoothing noise. Log support counts. Unknown lineage uses its recorded group and pooled backoff; unseen metadata maps only to unknown, never to a hidden condition. Invalid/corrupt calibration, negative/non-finite costs or probabilities, nonnormalized arrays, wrong schemas/versions, or a zero-probability acquired history yields DEFER with a diagnostic, never invented confidence.

The cost unit is median warm pilot R1 seconds. Predict costs from training-only per-action pooled medians divided by this frozen positive unit. Do not use test completion times to plan. Terminal costs are `20 × (1-p)` for acceptance and `5` for deferral, where `p=P(Y=1 | acquired history,g)`.

```text
J(h) = min(20 × (1-p), 5,
           min_j [predicted_cost(j)
                  + Σ_o P(oj=o | h,g) × J(h + (j,o))])
```

Only available unqueried checks enter the inner minimum. Posterior and predictive probabilities come from the same coherent joint array by exact marginalization. There are 81 outcome vectors per class and at most 256 histories per lineage before availability masks; memoize by calibration/config hash, lineage, availability, and history. Acquired genuine T=FAIL forces DEFER. Zero-cost checks still consume their one opportunity, so recursion terminates.

Tie order: stopping before acquiring; DEFER before ACCEPT when terminal costs tie; then lower predicted check cost and fixed `R1,R2,T,D` order. Use absolute numerical tolerance `1e-12` only for floating equality/normalization tests, not to declare research equivalence. Common actor/preflight costs do not change the argmin but are included in evaluated loss.

## 11. Baselines, tuning, and ablations

| Policy | Fixed definition |
| --- | --- |
| Always accept | Accept after valid common preflight |
| Always defer | Defer every proposal; charge 5 plus common work |
| T-only | Run T, accept only PASS; unavailable/UNKNOWN/FAIL means defer |
| Best single check | Train each check's three-verdict accept/defer map under the fixed losses; choose check on development |
| Best fixed sequence | Enumerate 24 orders; restricted I planner can stop or buy the next remaining action, never reorder; select on development |
| Source deduplication | Same selected order/rule, but never buy both R1/R2 under shared lineage |
| I | Independent likelihood, exact planner |
| J | Full joint likelihood, same exact planner |
| Generic learned pair | Same pair implementation; choose one of six pairs using four root-group training folds, alpha=16, held-out joint log loss; refit train and select alpha from the same three dev values |
| P | Fixed R1/R2 pair, provenance conditioning, exact planner |

Also evaluate P without lineage conditioning, I as dependence-removal, all-checks learned terminal policy as a costed evidence diagnostic, and optionally a clearly marked label-aware hindsight oracle. None is an oracle baseline presented as deployable performance.

Choose the **baseline champion from deployable baseline rows excluding P**, and excluding ablation/diagnostic/oracle rows. Freeze it before test collection. Select minimum development objective with practical ties toward simpler policies. A concrete preregistered tie convention is relative loss difference at most 1% of the minimum; prefer fewer learned parameters, then fewer expected acquired checks, then listed order. This selection convention does not replace the research gates or define statistical equivalence.

Report every baseline, structure-selection CPU work, table size/support, fit time, and chosen alpha. P receives no extra features/data/planner/search budget. Generic learned-pair choosing R1/R2 and matching P defeats a distinctive hand-specified structure claim, even if dependence helps.

For the brief's qualitative “matches at the study's resolution” condition, require an actual contrast: if a generic/simple comparator has the same useful trajectories or practically dominates P, claim C fails; if differences remain unresolved, claim C is unestablished and the stage is INCONCLUSIVE. Do not turn absence of significance into equivalence or invent a new numeric acceptance threshold after seeing outcomes.

After freezing primary settings, report the nine penalty pairs from wrong accept `{10,20,50}` × defer `{2,5,10}`. Replay the fixed primary policies and rescore their trajectories under each pair, preserving acquisition/terminal rules, learned parameters, and champion identity. This literal fixed-policy sensitivity does not refit or search for a better policy at each weight. These CPU sensitivity replays cannot rescue the primary endpoint. Report warm and cold costs separately.

## 12. Statistics, objective, and economics

Per episode, deployment loss is:

```text
L = (actor_seconds + preflight_seconds + selected_check_seconds
     + controller_seconds + apply_or_defer_wrapper_seconds) / pilot_unit
    + 20 × I(ACCEPT and Y=0) + 5 × I(DEFER)
```

Average episode quantities within root, then weight roots equally. Keep raw counts visible. Paired comparisons use identical eligible episodes and resample complete root blocks with all policies together, 10,000 resamples, fixed seed. Use percentile paired block-bootstrap intervals for differences and latency ratios, report ordinary two-sided 95% intervals, and one-sided 97.5% upper bounds for the two confirmatory contrasts P−champion and P−I. Both upper bounds must be below zero for combined success; if champion=I there is only one distinct comparison. The [SciPy bootstrap reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html) supports paired resampling and cautions about degeneracy; the root-block unit and interval choice here are study decisions.

Seconds per correct accepted patch is root-weighted mean total seconds per attempted task divided by root-weighted correct accepts per attempted task; with equal root sizes it equals total time/correct accepts. Use the same functional in bootstrap replicates. Zero correct accepts yields undefined/infinite cost, never zero. If any resample prevents a ratio estimate, mark the affected interval non-estimable and report its frequency; never discard those resamples. Report task-class-level grouping sensitivity and downgrade conclusions if root independence is implausible.

For sparse failures show raw paired outcomes and exact binomial intervals only for defensibly independent group-level events, using the [SciPy binomial interface](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html). Zero events give one-sided 95% upper bound `1 - 0.05**(1/n)`: approximately 8.94%, 4.57%, and 2.31% at n=32,64,128. A group-event bound is not a per-patch guarantee. The observed quality guardrails are not statistical safety non-inferiority.

The main policy table contains episodes/roots, intended/excluded/unresolved denominators, correct accepts/incorrect accepts/deferrals, both accept types per attempted task, incorrect fraction among accepts, normalized loss and paired differences/intervals, verification/total seconds, seconds per correct acceptance, acquired counts by check, UNKNOWN/timeout/format rates, warm median/p95, and separate cold-start cost. Diagnostic probability scores include held-out log loss/Brier score, agreement histories, calibration support counts; no test recalibration or tiny-bin confidence claims.

Keep deployment work, research/calibration work, and assumed outcome penalties separate. Report real latency, tokens, model-active/wall time, disk, and fitting work; no invented API dollars or energy estimate. For each simpler baseline, calculate extra calibration work / future per-task work saved in matching units. Nonpositive savings has no break-even. Show scenarios for 100, 1,000, and 10,000 tasks; T-only inherits no unnecessary fitting cost.

## 13. Required verification properties

| Concern | Required evidence |
| --- | --- |
| Probability/DP | Normalization, marginalization, prior recovery, total probability, DP versus independent exhaustive value; all histories/masks finite and terminating |
| Economic controls | Independent, copied, mixed-modality, useless, free/expensive perfect, asymmetric, XOR-like, zero/unknown support, dominant cheap test; dependence sometimes helps and sometimes does not |
| Copied evidence | Correctly specified duplicate adds no posterior evidence; genuine action charged, accidental repeated request rejected without charge |
| Leakage | Changing any unrequested outcome cannot change the next action; label perturbation cannot change any complete trajectory; no condition-name features |
| Failure accounting | Malformed/truncated/UNKNOWN/timeouts retained; candidate versus infrastructure distinguished; replay charges original cost; all-defer costs nonzero |
| Files/cache | Stale proposal/environment/model/prompt/source invalidates applicable evidence/calibration; traversal/symlinks/protected writes rejected; accept idempotent |
| Budget/resume | Reservations never overspend; denied call has no side effect; interrupted events reconcile without free work or duplicate examples |
| Isolation | Hostile container fixtures bounded; no hidden source/output mounted; no host fallback; missing cleanup blocks next action |
| Benchmark | Contract/reference/mutant agreement, genuine root separation, no clone-inflated sample size, unresolved ledger |
| Statistics | Root block resampling, policy pairing, degenerate ratios, zero accepts, sparse support and confirmatory duplicate contrast handled |
| Live | Both terminal actions affect only intended disposable copies; sequential acquired outcomes reproduce trajectory; changed verdicts distinguished from replay bugs |

M0 implements the mathematical/protocol subset with fakes. Runner fixtures require M1; labeler and collection checks appear with their owning milestone. Never claim a fake runner proves real execution isolation.

## 14. Detailed research gates and panels

### M0: mathematical and harness checks

GO only when known-table expected and exhaustive realized costs agree within tolerance, controls behave as specified, label/unrequested-outcome perturbations cannot alter policy behavior, all paths terminate, permissions hold within temporary test directories, and costs reconcile. Failed tests are BLOCKED. Toy success is implementation evidence only. Recreate the brief's controls in tests; its reported earlier 16 checks and illustrative losses are supplied background, not results already run here.

### M1: machine, model, and runner smoke

Use pilot materials, a preregistered few proposal/review calls and repeats, plus every hostile runner fixture. Record cold load, warm prompt/generation rates, peak memory, container overhead, power state, parser success, and rerun text-versus-verdict variation. GO requires all ordinary smoke/isolation tests, at least 90% valid review parses, no hidden context leak/silent truncation/serious swapping, and M2 projection within its margin-adjusted cap. Unavailable isolation, incompatible model, unreliable termination, or resource failure is BLOCKED. A smaller setting or shorter representation is possible only before experimental freeze, recorded explicitly.

### M2: pilot headroom

Collect 24 natural episodes, all available checks, and a separate eager-grounded actor+T system on eight pilot IDs fixed beforehand. That alternative receives all allowable documentation up front and pays extra input cost. Different proposals make it a separate system-level comparison on matched tasks, not a paired verifier ablation on identical patches.

Inspect the correctness/evidence/cost matrix, conditional verdict frequencies, errors uniquely exposed by check type/root, R1/R2 dependence by provenance, strongest simple policies, and errors left after T/eager grounding. Audit predetermined full traces and every label inconsistency using actual contracts/code/counterexamples; do not invent human review.

GO requires all: at least five correct and five incorrect natural proposals; complementary useful checks of at least two types across at least three roots; at least one genuine incorrect public-PASS proposal with corrective evidence elsewhere; plausible acquisition headroom beyond a dominant cheap check; no leakage/false source independence/evaluator defect; and next-stage budget feasibility. Malformed failures alone do not establish useful headroom. Cheap tests, a single check, eager grounding, always accept, redundant errors, or prohibitive diagnosis can cause NO_GO. Insufficient natural errors/diversity is INCONCLUSIVE, with only the one bounded fresh-root revision described in §3.

### M3: train/development challenge

After benchmark/split/source lock, collect 96 train and 48 development episodes. Require at least 20 correct and 20 incorrect mechanically valid training proposals, and disclose actual complete fitting support. Otherwise stop INCONCLUSIVE without expansion/rebalancing.

Implement the entire baseline ladder and required ablations. GO requires: P development mean loss at least 10% below champion; no more incorrect accepts and no fewer correct accepts; benefit decreases under dependence removal; acquisition changes span more than one root; J/learned-pair/dedup has not explained away the result; benefit exists in natural proposals; remaining sample/budgets are frozen and feasible. Support uncertainty is INCONCLUSIVE; quality regression or sufficient simpler/generic policy is NO_GO. Repair implementation defects transparently; permit at most one documented substantive mechanism revision before M4.

### M4: locked evaluation

Before test proposal generation write `frozen_run.json` with code/config/split/model/tokenizer/image/source hashes, all policy definitions/parameters and smoothing, champion, objective/unit/costs, sample size, seeds, timing/selection rules, and gates. Reject changed inputs or any fitting on test outcomes/labels. Collect 128 episodes once, replay all frozen policies, and reconcile all counts/costs/labels.

Candidate success requires all seven brief conditions:

1. P mean loss at least 10% lower than the frozen champion.
2. Paired root-level 95% loss-difference interval upper endpoint below zero, and the adjusted confirmatory requirement in §12.
3. No more incorrect accepts and at least as many correct accepts as champion in the observed test sample.
4. Actual end-to-end seconds per correct accepted patch at least 10% lower, with point estimate and interval disclosed.
5. At least 20 correct accepts across at least eight roots.
6. Dependence-removal benefit points in the predicted direction and its held-out interval is reported; validated B requires the adjusted P−I upper bound below zero.
7. No practical domination by another baseline in the complete table; a matching simpler mechanism cannot be ignored.

GO to M5 requires both efficiency and mechanism evidence. Favorable points with unresolved intervals/mechanism evidence are INCONCLUSIVE. No useful gain, observed quality regression, or sufficient simpler/generic comparator is NO_GO. Do not change weights, sample, seed, or classes after the result.

### M5: live and stress panels

**A — live:** 16 fresh episodes from at least four fresh roots, small two-file repositories. Generate one proposal per episode. Run P/champion independently in randomized order against that frozen proposal using actual requested calls only. Apply to separate disposable copies and grade after both decisions. Record real warm-session/cold-start conventions. Replay each actual trajectory from its acquired outcomes. Different model verdicts across repeated calls are nondeterminism, not automatically a replay defect.

**B — source/availability:** 16 existing proposals chosen by a fixed ID rule, keeping candidates and labels fixed. Before calls, freeze a balanced assignment to copied source lineage, missing lineage metadata, contradictory/outdated documentation, and unavailable D; rerun only affected checks. This is a separate controlled panel. Run CPU label-conditional R2 recombination within `(Y,lineage)` to vary coupling while preserving marginals; fewer than two exchangeable observations makes a stratum unavailable. Never expose intervention labels or use this diagnostic as natural performance or policy input.

**C — grounding/seed:** eager-grounded actor+T on the 16 fresh episodes, with separate own-proposal costs/labels. Repeat a predetermined eight-episode subset with a second actor seed and fresh review calls. Pre-register exactly which policies/checks are executed for these repeats and include them in the 2-hour forecast; do not add repeat panels after seeing results.

Require no leakage, stale PASS, duplicate side effects, or unbounded work; both accept/defer file paths work; actual costs retain the direction of savings without overhead erasing it; copied-source diagnostics do not invent confidence; version changes invalidate evidence/calibration; fresh tasks/second seed show no obvious quality collapse; eager grounding does not eliminate the need. Leaks/unsafe paths are BLOCKED execution, substantive simpler-workflow failure is NO_GO, and small unresolved reversals are INCONCLUSIVE. No online refitting on M5 labels.

### M6: final report

Assign exactly one of `LOCAL_POC_PASS`, `NO_GO`, `INCONCLUSIVE`, plus optional execution `BLOCKED`. A local pass requires locked efficiency/mechanism success and no material live/stress contradiction. Headline the exact model, task population, sample, cost assumptions, uncertainty, and limits on risk inference. A NO_GO must distinguish A/B/C and preserve positive simple/generic findings. An INCONCLUSIVE names the unresolved quantity. Do not recommend scale as the default remedy.

Report every baseline, one main results table, a few fixed-rule traces, principal failures, uncertainty, natural versus controlled panels, three cost categories, break-even scenarios, artifact links/hashes, and unexecuted stages. Freeze existing artifacts and reproducibility instructions even after an early stop; later unused machinery remains unbuilt. No M6 model runs.

## 15. CLI and reproducibility contract

These are future interfaces, not commands available in this documentation-only repository:

```bash
python -m pip install -e '.[dev]'
python -m depverify doctor --fake
python -m depverify simulate --suite core
python -m pytest -q

# M1, only after M0 GO; pin the verified working version afterward.
python -m pip install mlx-lm
python -m depverify doctor --local
python -m depverify smoke --config config.toml

python -m depverify collect --split pilot --resume
python -m depverify evaluate --stage pilot
python -m depverify collect --split train --resume
python -m depverify collect --split dev --resume
python -m depverify fit
python -m depverify evaluate --stage dev
python -m depverify freeze
python -m depverify collect --split test --resume
python -m depverify evaluate --stage test --locked
python -m depverify live --panel fresh
python -m depverify stress --panel sources
python -m depverify challenge --panel eager-grounding
python -m depverify report
```

Every collection command supports `--dry-run`: count, token ceiling, measured estimate or explicitly unavailable estimate, remaining stage/global budgets, and required gate. Dry-run performs no model download/call or candidate execution. Expensive commands reject missing/failed/stale gates. No generic gate bypass exists. Tiny fake/smoke fixtures are explicitly ineligible for claims. `report` always works on the completed evidence prefix.

Reproducibility artifacts include setup/pins/revisions and exact commands; minimal tested code; task/source/split manifests; private evaluation definitions; immutable proposals/checks/labels and attempts; budget ledger; policy parameters; `frozen_run.json` where reached; report and manifest linking preserved run data. Hashes and references accompany large ignored artifacts; a report must not link to unavailable evidence.

## 16. Traceability and interpretation decisions

| Brief sections | Specification coverage | Implementation ownership |
| --- | --- | --- |
| 1–3: purpose, stack, cascade, limits | §§1–4, 8–9, 14 | M0 core, M1 machine/runner |
| 4–5: tasks/checks/labels/isolation | §§5–8 | M0 fake boundaries, M1 pilot/evaluator |
| 6: collection/replay/stochasticity | §§5, 9 | M0 protocol, M2 real collection |
| 7: probability/planning | §10 | M0 known tables, M3 fitting |
| 8: baselines/ablations | §11 | M2 screening, M3 full ladder |
| 9: research gates | §§3, 14 | Each owning milestone |
| 10: statistics/economics | §12 | M0 accounting, M3/M4 inference |
| 11: failure cases | §13 plus detailed sections | Explicit tests in the plan/roadmap |
| 12: CLI/artifacts | §§4, 15 | Incremental by milestone |
| 13: expansion | §17 | Outside this experiment |
| 14–15: prior reviews/sources | §§1, 14, 18 | Context only, not new results |

The following resolve ambiguity without changing the brief's research thresholds: two separate locks; champion excludes P and diagnostics; stage exhaustion checkpoints instead of silently deferring uncollected tasks; the M3 development comparison is exploratory and M4 is locked; all natural malformed proposals remain in outcome metrics while likelihood fitting uses valid resolved evidence; missing actions are different from observed UNKNOWN; runtime revisions are measured/pinned later. The 64 KiB proposal cap, numeric tolerance, percentile interval convention, and 1% champion tie convention are design choices recorded before results.

Machine/package/image facts, observed runtime, exact pilot task IDs, pressure sampling, and repeat-panel schedules must be resolved at their owning milestones before use. Their absence here is intentional: inventing measured values or creating a large benchmark during planning would violate the experiment. No core requirement or gate is delegated to unspecified future judgment.

## 17. After a local pass

Only after LOCAL_POC_PASS choose one next uncertainty: stronger fitting local model with fresh calibration/test, a broader pinned repository workload, or a second model family/verifier menu. External GPU work requires a new written study identifying measured capacity/throughput limitation, baseline, sample, and hard budget. It cannot fix weak labels, failed ablations, leakage, or inconclusive evidence. No automatic new architecture, RL, repair loops, embeddings, graph store, or human-review service.

## 18. Source context

The supplied sources support existing methods/tool capabilities, not expected gains or local results. Relevant pages were consulted while preparing these documents; exact working versions still require M1 verification.

- [Distribution Guided Active Feature Acquisition](https://arxiv.org/html/2410.03915v1): dependency-capable acquisition context; J is an ordinary small baseline, not a reproduction claim.
- [Rational Metareasoning for Large Language Models](https://arxiv.org/abs/2410.05563): allocation of inference computation as prior work.
- [SABER](https://arxiv.org/html/2512.07850v1): safeguards around mutating actions; its full workflow is outside this PoC.
- [Correlated Errors in Large Language Models](https://arxiv.org/html/2506.07962v1): motivation to measure shared errors, not evidence for this check menu.
- [Docker Desktop on Mac](https://docs.docker.com/desktop/setup/install/mac-install/): local compatibility/prerequisites to verify at M1; use an existing compatible engine.
- [Fallback upstream Qwen model](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct): record if the resource/setup fallback is used.

Model, MLX, Docker execution/security, and statistical sources are linked beside the requirements they support. Protocol thresholds and implementation choices come from the project brief and this specification.
