# Execution and review record

Work stayed on the user-requested current `main` branch. The nine M0 tasks each have a focused commit and a passing test record. A fresh reviewer checked the whole M0 range `868090c..0e174eb` read-only and independently passed 186 tests. The three Important findings were reproduced and corrected in one TDD pass, committed as `f581536`; the resulting suite passes 197 tests. The subsequent gate verification reran dependency, fake doctor, core simulation, pytest, and whitespace checks against unchanged source/config fingerprints. No second review was commissioned.

The 11 added cases cover direct and loaded overflow tables, parent-symlink and directory replacement, and failed-check status/check-ID consistency. Ten failed on the old implementation; the JSON rejection case already passed. [Red](../runs/m0/review/regressions-red.txt) and [green](../runs/m0/review/regressions-green.txt) outputs are retained. Historical gate evidence referring to skill scratch is relocated through the M0 artifact manifest; raw bytes and hashes are preserved.

Rulings, in order, with their practical limits:

1. Work on current `main`: explicitly requested. Cost if wrong: commits directly change this branch rather than an isolated branch.
2. Use installed Python 3.12.9: 3.11 was unavailable; the spec permits another supported installed version, and pinned dependencies passed. Cost if wrong: portability to an untested interpreter needs verification.
3. Real inference, container isolation, hostile execution, and machine feasibility are outside M0. M1 resource probes ran; real smoke/isolation did not. Cost if wrong: stack behavior remains unmeasured and requires an M1 attempt.
4. Real cache retrieval and collection-time metadata reconciliation belong to M1/M2. Current tests establish key sensitivity only. Cost if wrong: stale evidence or duplicate billing could invalidate later collection.
5. Full-evidence public-FAIL versus hidden-label audits when T was unrequested belong to collection. Current acquired-history contradiction checks cover the fixed fake fixtures. Cost if wrong: a later benchmark may have inconsistent labels.
6. Fitting, bootstrap precision, confirmatory inference, and real efficiency belong to M3/M4. Current equal-root aggregation is arithmetic, with no empirical claim. Cost if wrong: toy results could be mistaken for scientific evidence.
7. Power-loss durability was not fault-injected. Process interruption and partial-tail recovery are covered; no power-loss certification is claimed. Cost if wrong: recent records may need recovery after a power outage.

Deferred minor: fake policy hashes identify callable names, so different `make_policy` closures can collide. Do not use these identifiers for empirical multi-policy attribution. Implement frozen policy artifact hashing before the M3 comparisons. This does not change the fixed single-policy M0 fixture's observed result.
