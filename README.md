# Dependency-aware verification

A Mac-first research project testing whether shared-source dependency modeling makes a coding agent's verification decisions more useful and economical.

The implementation runs exact finite-horizon planning, masked evidence replay, disposable-file application, and budget accounting. M1 adds a bounded Docker runner, 24 validated pilot contracts, private host-side grading, and one serial native MLX worker. Fake commands import no MLX and execute no candidate code.

The [M0 result](reports/m0.md) passed. The [M1 result](reports/m1.md) is BLOCKED: the model kept wrapping proposals in Markdown, which the raw-Python contract rejects. The scientific result is INCONCLUSIVE; no natural pilot was collected. Storage now uses expected additional bytes on each affected filesystem, a 1.5× margin, and 1 GiB headroom. The prior workspace-only disk stop was unnecessary and remains a historical checkpoint.

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

Run artifacts are written under ignored `runs/m0/`. Each simulation has its own immutable attempt directory containing proposals, checks, decisions, separate private fixture labels, toy probability tables, and an actual-work ledger. Synthetic check costs are explicitly marked and are separate from actual CPU time. `core.json` points to the latest simulation; `report` summarizes available artifacts. A simulation alone never writes a GO gate.

`doctor --local` records actual hardware, power, engine availability, storage paths, and preliminary per-filesystem estimates. It does not certify the smoke gate. `smoke --config config.toml` requires current M0 verification and the recorded runner/model/admission inputs. Its failed attempts remain under `runs/m1/smoke/`; malformed code is preserved, never stripped or regenerated into success. [M1 setup and exact checks](reports/m1.md) include the immutable model/image revisions. `report` summarizes the executed prefix.

Build the next milestone, run its checks, and continue only after its recorded gate is GO. Failed research gates end collection; environment failures are BLOCKED rather than negative scientific findings. Verify the actual uncached asset/staging sizes and free space on their destination filesystems before proceeding. No gate-bypass flag or host-execution fallback exists.
