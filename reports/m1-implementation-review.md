# M1 implementation review

One fresh read-only reviewer checked `4ddb743..1c771a0` and independently passed 232 ordinary tests. No model generation, download, or real candidate execution was performed by that reviewer. No second review was commissioned. The five Important findings were reproduced and fixed in one TDD pass, committed as `9780d43`; the ordinary suite then passed 244 tests.

| Finding | Fix / evidence |
|---|---|
| IPC outside model watchdog | Nonblocking bounded framing; blocked sender and partial-frame receiver RED→GREEN; termination, settled costs, restart checked |
| Candidate/infrastructure label confusion | Actor infrastructure remains unresolved; container state proves a started candidate's exit before marking candidate failure; both directions RED→GREEN |
| Operational cache double counting | Actual model digests and pinned image inventory verified; cached downloads contribute zero incremental bytes; 3 GiB destination regression RED→GREEN |
| Unverified loaded model identity | Missing, changed, and unexpected asset inventory rejected before worker load; retained verified digest identity |
| Empty/stale prerequisites accepted | Complete hostile fixture/task sets required; XML hash plus relevant code, benchmark, and image bindings checked |

Deferred Minor: the M1 preflight manifest is stored under `preflight_seconds`, though its numeric `elapsed_seconds` remains inside that manifest. No empirical cost calculation uses that misnamed field. Correct the presentation before relying on it in later empirical accounting. The earlier M0 Minor (closure-name policy hash collisions in the fake flow) also remains deferred until empirical multi-policy artifact identities are needed.

The review confirmed that three fenced proposals justify M1 BLOCKED under the ordinary-smoke requirement, even when review JSON parsing passes. The user then explicitly requested continuation; M1 setup continued with one fixed public formatting example. This is a prompt-wrapper setting, not repair of an earlier proposal, a favorable natural retry, or a research threshold change. All earlier smokes and costs remain retained.

Reviewer limitations remain visible: it did not independently test new engine interruptions/delayed creation, prove kernel escape resistance, regenerate MLX timing/output, or assess unexecuted M2–M5 results. The local container is a bounded research boundary, not a hostile shared-hosting guarantee. The enumerated parser evaluator does not establish behavior for every Unicode line separator.
