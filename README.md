# Dependency-aware verification

A Mac-first research project testing whether shared-source dependency modeling makes a coding agent's verification decisions more useful and economical.

The implementation runs exact finite-horizon planning, masked evidence replay, disposable-file application, and budget accounting. M1 adds a bounded Docker runner, 24 validated pilot contracts, private host-side grading, and one serial native MLX worker. Fake commands import no MLX and execute no candidate code.

The [M0 result](reports/m0.md) and [M1 smoke](reports/m1.md) passed. The [M2 pilot](reports/m2.md) resumed on 3 October after memory pressure cleared and completed all 24 natural episodes plus eight eager-grounding comparisons. Only three natural proposals were correct, below the five required, and the implemented four-check sequences showed no economic selection headroom. The scientific result is **INCONCLUSIVE**; collection has stopped at this research gate. A later exploratory shorter sequence reduced incorrect accepts, but did not beat always defer under the declared objective; it does not change the gate. Full fitting, held-out evaluation and live panels remain unexecuted. Storage uses additional uncached bytes on each actual filesystem, a 1.5× margin and 1 GiB headroom; the blanket 20 GiB repository rule has been removed.

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

Run artifacts are written under ignored `runs/`. Each simulation has its own immutable attempt directory containing proposals, checks, decisions, separate private fixture labels, toy probability tables, and an actual-work ledger. Synthetic check costs are explicitly marked and are separate from actual CPU time. `core.json` points to the latest simulation; `report` summarizes M0/M1 artifacts; [the current research report](reports/final.md) includes the complete M2 pilot. A simulation alone never writes a GO gate.

`doctor --local` records actual hardware, power, engine availability, storage paths, and preliminary per-filesystem estimates. It does not certify the smoke gate. `smoke --config config.toml` requires current M0 verification and the recorded runner/model/admission inputs. Its failed attempts remain under `runs/m1/smoke/`; malformed code is preserved, never stripped or regenerated into success. [M1 setup and exact checks](reports/m1.md) include the immutable model/image revisions. [The current result](reports/final.md) summarizes the executed prefix.

Build the next milestone, run its checks, and continue only after its recorded gate is GO. Failed research gates end collection; environment failures are BLOCKED rather than negative scientific findings. Verify the actual uncached asset/staging sizes and free space on their destination filesystems before proceeding. No gate-bypass flag or host-execution fallback exists.

M2 commands are `collect --split pilot --resume --dry-run`, `collect --split pilot --resume`, and `evaluate --stage pilot`. Collection rejects missing/stale GO prerequisites before a model call; later splits remain unavailable. Completed bad outputs retain their original costs on resume. The recorded freeze identifies the exact collection code and inputs. [Pilot plan](docs/superpowers/plans/2026-09-29-m2-evidence-pilot.md), [result and resume conditions](reports/m2.md).
