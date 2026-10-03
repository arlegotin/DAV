# Contributing

The recorded study ended at M2 with NO_GO for its special controller. Contributions can improve the reusable harness, reproduce results, find protocol defects, or investigate a genuinely different evidence menu. A new study must keep its results separate from these pilots.

Use the CPU setup in the [README](README.md). Before proposing a change, run:

```bash
python -m pytest -q
python -m depverify simulate --suite core
python examples/replay_pilots.py
git diff --check
```

The ordinary suite excludes eight opt-in real-container fixtures. Model collection and native smoke testing require the documented bound prerequisites; CI runs only CPU tests and saved-evidence replay. Do not execute generated proposal code on the host.

For a bug fix, include a regression that fails before the fix and passes afterward. Explain the observable failure, resulting behavior, and checks run. Keep changes small and avoid adding services or frameworks to this finite experiment.

Treat published artifacts as historical data. Preserve malformed proposals, UNKNOWN outcomes, costs, root identities, and separate natural/eager panels. A discovered label or evaluator defect needs an explicit erratum with its counterexample and affected denominators, not an undocumented replacement. Do not silently change penalties, thresholds, seeds, exclusions, or task difficulty to improve the result.

A follow-up proposal should name its question, strong simpler baseline, independently grouped tasks, fixed budget, and stop rule. Show useful complementary verification evidence before building a more elaborate acquisition mechanism. The current run does not automatically expand or inherit calibration across model/check versions.

When filing a reproducibility issue, include the commit, Python/platform versions, exact command, and relevant error. Keep credentials and unrelated machine/process details out of logs. The published records already replace local filesystem paths; preserve that convention.

Code, documentation, and original benchmark/artifact contributions are under the repository's [MIT license](LICENSE). External model weights and dependencies are not bundled and retain their own licenses.
