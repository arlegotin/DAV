# Dependency-aware verification

A Mac-first research project testing whether shared-source dependency modeling makes a coding agent's verification decisions more useful and economical.

The M0 implementation runs exact finite-horizon planning, masked evidence replay, disposable-file application, and budget accounting with fake checks. It does not execute generated code or call a model. Toy results establish harness behavior; the research hypothesis is still untested.

The recorded [M0 result](reports/m0.md) is GO: 186 tests and 25 core controls passed. Its [artifact manifest](reports/m0-artifacts.json) binds the code/config fingerprints and local evidence. M1 is the next permitted milestone.

- [Project specification](docs/superpowers/specs/2026-09-29-dependency-aware-verification-design.md): architecture, evidence boundaries, research protocol, budgets, baselines, statistics, and stop conditions.
- [Implementation plan](docs/superpowers/plans/2026-09-29-dependency-aware-verification.md): detailed M0 tasks and a conditional M1–M6 roadmap.

The tested environment uses Python 3.12.9. Create a local environment and install the recorded versions:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-build-isolation --no-deps -e '.[dev]'
python -m pip check
python -m depverify doctor --fake
python -m depverify simulate --suite core
python -m pytest -q
python -m depverify report
```

`requirements.lock` records the working package versions, including the build backend. The ordinary editable-install interface is also `python -m pip install -e '.[dev]'`. MLX is a later, optional dependency and is not imported by fake commands.

Run artifacts are written under ignored `runs/m0/`. Each simulation has its own immutable attempt directory containing proposals, checks, decisions, separate private fixture labels, toy probability tables, and an actual-work ledger. Synthetic check costs are explicitly marked and are separate from actual CPU time. `core.json` points to the latest simulation; `report` summarizes available artifacts. A simulation alone never writes a GO gate.

Only the commands above are implemented at M0. Build the next milestone, run its checks, and continue only after its recorded gate is GO. Failed research gates end collection; environment failures are BLOCKED rather than negative scientific findings. Model collection and later CLI commands are added only when their preceding milestones pass.
