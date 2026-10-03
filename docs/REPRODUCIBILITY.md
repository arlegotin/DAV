# Reproducing and interpreting the result

## What a fresh clone can reproduce

The public snapshot includes both completed pilots: 24 natural and eight eager-documentation proposals each. They remain separate. The checked-in benchmark contains all public contracts and research-only evaluator definitions. Portable run copies live under `artifacts/pilots/`.

```bash
python examples/copied_evidence.py
python examples/replay_pilots.py --verify-only
python examples/replay_pilots.py
python examples/replay_pilots.py --json
python -m depverify simulate --suite core
python -m pytest -q
```

Replay verifies inventory hashes and exact completed bundles, runs the fixed policies through the existing masked interface, compares their trajectories with the saved decisions, and recomputes every saved natural score. It charges recorded actor/preflight/check/controller time, not current CPU/cache time. The fresh paired interval is reproduced with 10,000 root-group bootstrap resamples, seed 7305. Eager acceptance counts are replayed separately; their original cost summary remains in the reports, since per-episode eager controller timings were not retained.

These commands make no model call and execute no candidate program. They reproduce decisions and analysis from observations; they do not independently re-grade patches, reproduce native timing, or validate the sandbox on another host.

The [artifact guide](../artifacts/pilots/README.md) lists the included and omitted records. Published manifests are integrity/provenance checks, not proof that the underlying evaluator is universally correct. Every held-out/train/dev/live stage remained unexecuted.

## Dependencies

Use Python 3.12 for the recorded CPU/test pins in `requirements-core.lock`. Their NumPy/SciPy releases require 3.12 or newer. The package's broader Python metadata permits 3.11 with compatible dependency versions; that combination was not validated in this study.

`requirements.lock` retains the entire recorded native-model environment, including MLX packages. It is not the portable CPU install path. MLX imports lazily inside the native worker. The CLI reads repository assets, so the documented workflow is an editable source checkout, not a standalone installed wheel or PyPI release.

GitHub Actions is configured to run the CPU suite and published replay on Python 3.12/Linux, without model weights or containers. Its remote result becomes available after publication; local verification is reported separately.

## Recorded native collection setting

These details identify the experiment, rather than define the general idea:

| Item | Recorded setting |
|---|---|
| Native model | `mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit` resource/setup fallback |
| Model/tokenizer revision | `b3252a2f97102b1fb1571fec2c9b27219a8536be` |
| Upstream Qwen revision | `2e1fd397ee46e1388853d2af2c993145b0f1098a` |
| Inference | MLX LM 0.31.3, MLX/metal 0.32.3; one resident model and serial calls |
| Host | M3 Max, detected 36 GiB unified RAM, macOS 26.6.2, Python 3.12.9 |
| Execution image | `python@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f`, ARM64 |
| Image ID | `sha256:8630ab77c5adf06e1f914483db4dd70e3fa59118160daab9b0ee75e685344221` |
| Proposal/check caps | 3,072 input tokens; 512 proposal or 128 review output tokens; 4,096 total context |
| Candidate caps | 1 CPU, 512 MiB, 32 processes, ten-second outer timeout, 64 KiB output |
| Objective | Recorded work / pilot median warm R1 latency + 20 per incorrect accept + 5 per deferral |

The original and fresh cost units differ, so normalized losses should not be pooled or compared across pilots as if the unit were shared. Each within-pilot comparison uses identical frozen proposals and per-check costs. Both pilots have six root groups; four variants are one cluster, not four independent problems. All R1/R2 pairs have shared source lineage.

The model used safetensors, pinned immutable revisions, offline loading, and remote code disabled. Containers had no network, read-only mounts/root, dropped capabilities, no-new-privileges, a non-root user, bounded tmpfs, resource limits, and confirmed cleanup. Expected hidden outputs and reference code stayed on the host. No host-execution fallback exists. These controls are not certification of a hostile multi-tenant sandbox.

See [M1](../reports/m1.md), [original M2](../reports/m2.md), [fresh protocol](../reports/replacement-pilot-protocol.md), and [final audit](../reports/audit-2026-10-03.md) for settings, framing failures, admission checks, and recovery fixes. Collection executed at `989cb22`; later CPU-tested fixes are distinguished from the historical native authorization.

## Costs and limits

Measured retained work totals 370.83 model seconds and 504.76 container seconds, including failed setup calls, both pilots, and diagnostics. The [cost inventory](../reports/research-costs.json) distinguishes the main ledger from separate setup ledgers. Development/audit/download wall time was not comprehensively metered; energy was not measured. Saved pilot latency is a warm-session prefix, with no live application or startup-amortization claim.

The fresh pilot's zero wrong test-only accepts is not a safety bound. Original public tests accepted three wrong proposals. Reviews were brittle and source diversity was limited. Neither empirical dependence benefit nor advantage over a generic learned acquisition model was established: M2 stopped before fitting those comparisons.

## New experiments

The released artifacts are inert evidence, not runnable GO authorization. A future native study needs fresh model/image verification, isolated fixture/admission checks, current M0/M1 gates, measured runtime/resource estimates, and a separate frozen protocol. Changing prompt, model, runner, or source versions invalidates their applicable cache/calibration.

Do not rerun the recorded pilots to search for favorable outcomes. Start with a distinct question and useful evidence menu, preserve these negative results, and use an explicit new budget and sample. No automatic model upgrade, larger sample, or infrastructure expansion is justified by this study.
