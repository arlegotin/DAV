# Portable pilot evidence

This snapshot makes the completed study inspectable from a fresh clone. Its [manifest](manifest.json) records exported checksums, source checksums, and transformations. It comes from repository commit `ca64875`; source execution revisions are recorded separately inside the freezes and reports. No new inference, proposal generation, or candidate execution occurred during export.

| Panel | Natural / eager episodes | Root groups in natural panel | Recorded gate |
|---|---:|---:|---|
| [Original](original) | 24 / 8 | 6 | `INCONCLUSIVE` |
| [One fresh revision](replacement) | 24 / 8 | 6 | `NO_GO` |

Each panel contains:

- `episodes/`: replacement code, proposal metadata, fixed check verdicts/reasons, evidence, and exact completion bindings.
- `private/labels/`: host-side evaluator labels and deterministic counterexamples; `private/audit.json` records researcher inspection.
- `model-calls/`: every pilot model operation, including raw response text, request bytes, seeds, token counts, status, and latency.
- `container-calls/`: every raw pilot container invocation, output/status, staged-file hashes, costs, and cleanup confirmation.
- `replay-decisions.json` and `replay-scores.json`: all saved natural trajectories and per-episode deployment-prefix scores.
- `frozen-pilot.json` and `gate.json`: historical settings and research decisions. These copies authorize no future native work.
- Post-pilot economic/short-sequence/sensitivity diagnostics, explicitly separate from the primary gate.

[Framing panels](framing) retain both the qualified reviewer inputs and the failed intermediate broad framing change. Their labels are fixed public smoke fixtures, not natural episodes. [Internal final review](audit/final-review.md), [execution ledger](audit/execution-ledger.md), and [research budget ledger](work-budget.jsonl) preserve the audit context.

Completed proposal/check/evidence/label files are byte-identical to the retained local bundles. Only local filesystem paths in auxiliary freezes/raw records were replaced with `<checkout>`, `<home>`, `<model-cache>`, or `<temporary-directory>`. Exported hashes differ where paths changed; original hashes remain in the manifest. Sampling, outputs, labels, costs, thresholds, and gate decisions were not changed.

`private` is a role boundary: these materials were excluded from the evaluated model and policies during collection. They are intentionally public after the study. A researcher may inspect them; a new evaluated agent must still receive only the allowed task materials.

The full local archive also contains M0 verification, native M1 setup/smokes, admissions, safety fixtures, session profiles, and recovery checkpoints. Those larger machine-specific logs are **not** in this snapshot. Their historical hashes are in [the local inventory](../../reports/final-artifacts.json), with summaries in the reports. Pilot replay does not independently establish labels, native timing, or sandbox safety.

Run `python examples/replay_pilots.py` from the repository root. It verifies files, reproduces every saved natural trajectory and score, and prints the primary tables. It consults labels only after each decision and charges original measured costs. It never executes the replacement code, calls a model, writes gates, or starts containers. Candidate programs in these records are research data; execute them only through the isolated runner.
