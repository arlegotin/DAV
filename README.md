# Dependency-aware verification

A Mac-first research project testing whether shared-source dependency modeling makes a coding agent's verification decisions more useful and economical.

The implementation runs exact finite-horizon planning, masked evidence replay, disposable-file application, and budget accounting. M1 adds a bounded Docker runner, 24 validated pilot contracts, private host-side grading, and one serial native MLX worker. Fake commands import no MLX and execute no candidate code.

The [final result](reports/final.md) is **NO_GO for the extra dependency-aware mechanism in this local setting**. The single fresh pilot produced eight correct and 16 incorrect proposals; cheap public tests separated all of them in the specified evaluator, while reviews rejected correct patches and added cost. This supports a simple test-first workflow in this pilot, not a general safety or held-out success claim. The original 24-episode pilot remains separately INCONCLUSIVE. All natural attempts, failed smoke outputs, uncertainty, costs and the framing sensitivity are retained. Fitting, held-out evaluation and live panels remain unexecuted.

The audit corrected cleanup/resume, record validation, paired/root-weighted metrics, useful-evidence screening, input-mutation grading, timeout and reporting defects. The ordinary suite passes 291 tests; all eight real isolation fixtures passed at refreshed M1. Storage still uses incremental uncached bytes per actual filesystem, a 1.5× margin and 1 GiB headroom; the blanket 20 GiB rule remains removed.

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

`requirements.lock` records the actual Mac smoke package versions, including MLX and the build backend. The ordinary editable-install interface is also `python -m pip install -e '.[dev]'`; this installs only the CPU/fake dependencies. MLX is imported only inside the native worker.

Run artifacts are written under ignored `runs/`. Each simulation has its own immutable attempt directory containing proposals, checks, decisions, separate private fixture labels, toy probability tables, and an actual-work ledger. Synthetic check costs are explicitly marked and are separate from actual CPU time. `core.json` points to the latest simulation; `report` reads the recorded final status when available; [the current research report](reports/final.md) includes both separate M2 pilots. A simulation alone never writes a GO gate.

`doctor --local` records actual hardware, power, engine availability, storage paths, and preliminary per-filesystem estimates. It does not certify the smoke gate. `smoke --config config.toml` requires current M0 verification and the recorded runner/model/admission inputs. Its failed attempts remain under `runs/m1/smoke/`; malformed code is preserved, never stripped or regenerated into success. [M1 setup and exact checks](reports/m1.md) include the immutable model/image revisions. [The current result](reports/final.md) summarizes the executed prefix.

Build the next milestone, run its checks, and continue only after its recorded gate is GO. Failed research gates end collection; environment failures are BLOCKED rather than negative scientific findings. Verify the actual uncached asset/staging sizes and free space on their destination filesystems before proceeding. No gate-bypass flag or host-execution fallback exists.

M2 commands are `collect --split pilot --resume --dry-run`, `collect --split pilot --resume`, and `evaluate --stage pilot`. Collection rejects missing/stale GO prerequisites before a model call; later splits remain unavailable. Completed bad outputs retain their original costs on resume. The recorded freeze identifies the exact collection code and inputs. [Pilot plan](docs/superpowers/plans/2026-09-29-m2-evidence-pilot.md), [result and resume conditions](reports/m2.md).

The one replacement pilot is `collect --split pilot --revision interface-v1 --dry-run` followed, only with current prerequisites and an unused permitted revision, by `collect --split pilot --revision interface-v1`. Its fixed directory is `runs/m2-replacement`; arbitrary directories cannot create another pilot. Score retained completed records with `evaluate --stage pilot --run-dir runs/m2-replacement`. The run has reached NO_GO: no further expensive collection is authorized. Historical M1 GO is bound to collection commit `989cb22`; post-collection CPU guard fixes require fresh native validation for any future experiment.

[Audit and continuation spec](docs/superpowers/specs/2026-10-03-audit-and-bounded-continuation.md), [implementation plan](docs/superpowers/plans/2026-10-03-audit-and-bounded-continuation.md), and [replacement protocol](reports/replacement-pilot-protocol.md) document why one fresh pilot was justified and why it stopped. Public tasks and private evaluator definitions are checked in; generated immutable records remain under ignored `runs/`, linked and hashed by the report. Rebuilding `bench/private/build_replacement_pilot.py` is deterministic CPU-only construction; reference/mutant execution belongs exclusively to the isolated runner.
