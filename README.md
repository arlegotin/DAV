# DAV — Dependency-aware verification

Two code reviews can agree because both read the same outdated API documentation. Counting that agreement twice makes a patch look safer without adding much evidence. DAV tests whether a coding agent can recognize this dependence and spend its verification budget better.

**The study is complete. The proposed controller didn't earn its extra complexity on the tested evidence menu.** In the fresh pilot, public tests caught every specified error, while the model reviews rejected every correct patch or returned `UNKNOWN`. That left no useful work for the more elaborate controller to do.

The repository includes the planner, isolated execution harness, both pilots, failed outputs, and an offline replay of the published evidence. You can inspect what went wrong without downloading a model or running generated code.

## Why the idea matters

Freeze one proposed patch. A controller can request a test, a review, or a documentation check, then accept the patch in a disposable copy or defer it. Each check runs once and reports `PASS`, `FAIL`, or `UNKNOWN` plus its measured cost. There is no repair loop.

The controller uses source-lineage metadata to distinguish repeated evidence from independent evidence. A small mathematical example shows why: with a 50% prior and 80%-accurate reviews, one passing review gives 80% correctness probability. A copied second pass still gives 80%; two genuinely independent passes give about 94.1%. Those numbers illustrate the mechanism. They aren't model measurements.

The practical question is whether this distinction improves decisions enough to pay for acquiring and processing the extra checks. The [protocol](docs/superpowers/specs/2026-09-29-dependency-aware-verification-design.md) declares the costs, baselines, and stopping gates.

## What the pilots found

Each pilot used six root problems with four semantic variants each. Variants share a root; they aren't 24 independent problems. The check menu contained public executable tests, two differently prompted reviews with shared lineage, and a documentation review, using one frozen local model.

| Pilot | Correct / wrong proposed patches | Test-only correct accepts / wrong accepts / deferrals | Decision |
|---|---:|---:|---|
| Original | 3 / 21 | 3 / 3 / 18 | Inconclusive |
| One permitted fresh revision | 8 / 16 | 8 / 0 / 16 | Stop the proposed controller |

In the fresh pilot, test-only verification had mean loss **5.302**, against **6.296** for deferring every patch under the declared penalties. Its exploratory root-bootstrap difference was −0.993, with a 95% interval of **[−2.660, +0.262]**. The sample is too small to establish a reliable population improvement.

And the original pilot's tests accepted three wrong patches. A passing public test remains partial evidence. The fresh result supports stopping this controller for this menu; it doesn't make tests a general correctness guarantee or refute dependency-aware verification elsewhere.

Each pilot also retains eight eager-documentation proposals, reported separately. Learned fitting, the learned baseline ladder, held-out evaluation, and live/stress panels were **not run** after the screening gate failed.

[Full findings](reports/final.md) · [Original pilot](reports/m2.md) · [Fresh protocol](reports/replacement-pilot-protocol.md) · [Research audit](reports/audit-2026-10-03.md)

## Inspect and replay it

Use Python 3.12 on macOS or Linux. These CPU examples need no model weights, container engine, credentials, or external service after installation.

```bash
git clone https://github.com/arlegotin/DAV.git
cd DAV
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-core.lock
python -m pip install --no-build-isolation --no-deps -e '.[dev]'
python -m pip check

python examples/copied_evidence.py
python examples/replay_pilots.py
python -m depverify doctor --fake
python -m depverify simulate --suite core
python -m pytest -q
```

The replay verifies published hashes and reproduces every saved trajectory and score for the original 32 and fresh 68 fixed screening policies. It reads evidence without executing proposal code, calling a model, or changing a research gate. Use `--json` for machine-readable output or `--verify-only` to check the inventory.

`simulate` creates explicitly synthetic records under ignored `runs/`. Their success checks the implementation; it isn't another scientific result. See [reproduction details](docs/REPRODUCIBILITY.md) for the recorded environment and native inference adapter.

## What you can reuse

- [Probability tables](src/depverify/probability.py) and [planner](src/depverify/policy.py): exact posteriors and finite-horizon acquisition over four checks, with explicit costs and deterministic stopping.
- [Replay and evaluation](src/depverify/evaluate.py): acquired-outcome masking, measured-cost accounting, public-failure veto, and root-weighted summaries.
- [Isolated runner](src/depverify/runner.py): bounded candidate execution, watchdogs, output limits, and confirmed cleanup.
- [Benchmark](bench/public), [evaluators](bench/private), and [published artifacts](artifacts/pilots/README.md): 48 contracts across 12 roots, all 64 natural/eager proposal bundles, raw outputs, decisions, and provenance hashes.

Here, `bench/private` means hidden from the evaluated agent; the research definitions are published. Correctness means passing the specified evaluator. Proposal text is data and must only execute through the isolated runner.

The [artifact guide](artifacts/pilots/README.md) identifies the exported records and omitted local logs. Completed proposal/check/evidence/label bundles retain their original bytes; local paths were replaced only in auxiliary records. The historical full inventory isn't a manifest of today's checkout. The research used coding-agent assistance and internal reviews; no external peer review is claimed.

This study is finished. Independent reproduction, harness fixes, and separately scoped experiments with genuinely complementary checks are useful contributions. Keep the original failures, costs, and gates intact; see [CONTRIBUTING.md](CONTRIBUTING.md).

## Credit and reuse

By **Artem Legotin**. Original code is licensed under [AGPL-3.0-only](LICENSE); original prose and reports under [CC BY 4.0](LICENSES/CC-BY-4.0.txt). Preserve author credit when sharing covered material. [Licensing scope](LICENSING.md) explains the attribution terms, third-party exclusions, and earlier MIT releases.

If you build on the software, benchmark, findings, or ideas, please cite [CITATION.cff](CITATION.cff), link this repository, and identify the commit and pilot you used. Citation of independently reused ideas is a scholarly request, separate from the license obligations.
