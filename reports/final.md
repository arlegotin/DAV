# Dependency-aware verification: local result

**Overall: INCONCLUSIVE. Execution: BLOCKED at M1.** Storage is sufficient under the corrected rule, isolation works, and the native model runs within the measured budget. The blocker is proposal formatting: all three final smoke proposals contain Markdown fences, violating the raw-Python file contract. They were rejected and preserved, with no repair or resampling into success.

M0's 25 controls and ordinary tests pass. M1 added a tested container runner, 24 admitted pilot tasks, private grading, serial MLX inference, strict token/time caps, and a measured forecast. Two smokes used 69.71 model-active seconds. The final smoke passed review parsing (11/12), resource checks, and the pilot forecast; all ordinary proposal preflights failed. [M1 report](m1.md).

| Milestone | Result |
|---|---|
| M0 mathematical/harness checks | GO |
| M1 local envelope | BLOCKED on raw proposal format |
| M2 natural pilot | Unexecuted |
| M3 fitting/development | Unexecuted |
| M4 locked evaluation | Unexecuted |
| M5 live/stress panels | Unexecuted |
| M6 report/artifact freeze | Completed for the executed prefix |

Claims A (adaptive verification), B (dependency relevance), and C (special structure value) are **untested**. Every empirical baseline/ablation is unexecuted. Zero natural episodes means no empirical acceptance, risk, uncertainty, savings, or break-even estimate exists. This setup failure is not a negative scientific finding and does not justify more compute or a larger benchmark.

The unresolved quantity is natural verification headroom, which cannot be measured until this actor produces usable files through the specified interface. Revisions, task contracts, evaluator definitions, failed calls, costs, and measurements are retained. [Summary](m1-summary.json), [historical storage checkpoint](../runs/checkpoints/m0-storage-stop/final.md).
