# Dependency-aware verification: local result

**INCONCLUSIVE. Execution BLOCKED at M2 by sustained system memory pressure.** M0 mathematics/harness checks and M1 local smoke passed. Six natural actors ran before the memory checkpoint: five episodes completed, one is partial; 18 natural episodes and all eight eager comparisons remain unattempted. No research gate is reported as passed.

| Milestone | Result |
|---|---|
| M0 mathematics, isolation/accounting controls | GO; 25 controls |
| M1 local model / runner smoke | GO on the separately recorded 1.5B fallback |
| M2 natural pilot | BLOCKED; incomplete one-class prefix |
| M3 fitting / development | Unexecuted |
| M4 locked evaluation | Unexecuted |
| M5 live / stress panels | Unexecuted |
| M6 prefix report / artifacts | Completed for available evidence |

The final M1 stack uses Qwen2.5-Coder-1.5B-Instruct-4bit revision `b3252a2f97102b1fb1571fec2c9b27219a8536be`, native MLX on an M3 Max with detected 36 GiB RAM and macOS 26.6.2. The default 7B had critical memory pressure and was replaced under the specified fallback rule before research collection. All earlier costs and outputs are retained. [M1 report and exact pins](m1.md).

M2 stopped after warning pressure persisted for more than 30 seconds. It remained at warning level for 31 additional samples with no model loaded. Peak model allocation was about 1.56 GB; causal attribution of system pressure is unknown. No memory threshold, task, penalty, sample size or source relation was changed to continue.

All five completed labels are incorrect, including one malformed output; four share the chunking root. One wrong proposal passed public tests, but its review explanations did not identify the actual boundary error reliably. This incomplete, clustered prefix cannot establish useful verification headroom. Eager grounding, complementary errors across three roots, and adequate correct/incorrect support remain unresolved. [M2 evidence, all fixed screening policies, denominators and inspected traces](m2.md).

Claims **A** (adaptive verification helps), **B** (dependence matters), and **C** (special structured model is worthwhile) are **untested**. I/P/J, deduplication, learned-pair baselines, held-out comparisons and live deployment remain unexecuted. Every prefix policy has zero correct accepted patches, so cost per correct acceptance and calibration break-even are undefined. Observing no incorrect accepts for deferral/review rules is not a safety finding.

Model-active work totals **203.33 seconds**, including failed M1 setups and the incomplete M2 prefix. Actual action costs are retained separately from assumed 20-unit wrong-accept / 5-unit deferral penalties. Storage now checks additional uncached bytes per destination filesystem with a 1.5× margin and 1 GiB reserve; it no longer imposes a blanket 20 GiB repository rule.

The unresolved quantity is natural verification headroom under a complete, resource-valid pilot. This setup interruption is not a scientific NO_GO and does not justify expanding compute, tasks or mechanism complexity. Immutable calls permit resume under unchanged frozen inputs once resource conditions permit it. [Artifact hashes](final-artifacts.json), [M2 summary](m2-summary.json), [review record](m2-implementation-review.md).
