# Changelog

## [0.9.0] — 2026-09-10 — all 8 roadmap phases implemented

Feature-complete against ROADMAP.md. Pre-1.0 pending real-world validation
(SWE-bench stub, `--remote` untested against a live host).

- **Phase 8** — `hydra run --remote <host>` (rsync repo → ssh `hydra run` →
  rsync `.hydra/` back → `git fetch` the branches); `hydra run/plan
  --from-overpower` reads `.overpower/plan.md`; `skills/using-hydra/SKILL.md`.
- **Phase 7** — `hydra reflect` → `.hydra/roles/<role>.lessons.md` (prepended by
  `load_role`); `eval/run_eval.py` + the `two-helpers` case; SWE-bench documented
  as a stub.
- **Phase 6** — `[routing]` model-per-role; `[policy]` allowed/forbidden paths +
  max files, enforced pre-dispatch; `hydra serve` stdio MCP server.
- **Phase 5** — `hydra merge`: `rule`/`agent` review gate + dependency-ordered
  merge into `hydra/run-<id>`; `[budget].tokens` ceiling.
- **Phase 4** — 5 built-in roles + repo overrides; shared memory
  (`context.md` + SQLite FTS); `.hydra/hooks/` lifecycle hooks.
- **Phase 3** — `hydra run` parallel dispatch (governor-capped ThreadPoolExecutor),
  `.hydra/runs/<id>/` state, `hydra status`/`resume`, `FAILURES.md`.
- **Phase 2** — worktree manager; `claude`/`qwen`/generic drivers; `hydra dispatch`.
- **Phase 1** — task model; file-set independence proof; `hydra plan`.
- **Phase 0** — scaffold; hardware governor; `hydra doctor`.

82 tests. stdlib-only core (Python 3.12+, `subprocess` + `git` + `sqlite3`).
