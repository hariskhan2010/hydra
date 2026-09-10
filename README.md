# hydra

**A multi-agent orchestrator for coding-agent CLIs.** Runs specialized agents in
parallel across git worktrees, with shared memory and a review-and-merge gate.

Everything [Ruflo / Claude Flow](https://github.com/ruvnet/ruflo) does — parallel
swarm, shared memory, hooks, MCP, model routing, resumable runs — plus what it
doesn't:

- **Agent-agnostic** — `claude -p`, `qwen -p`, `codex`, any OpenAI-compatible CLI. Not Claude-only.
- **Hardware-adaptive** — a governor caps concurrency to your free RAM and cores. Never OOMs the box.
- **git-native state** — every run, context update and merge is a reviewable, revertable diff.
- **No silent failures** — every dropped task or failed gate lands in `FAILURES.md` and on stdout.
- **Honest** — parallelizes only tasks with provably disjoint file sets; every perf claim links to a reproducible `eval/` script.
- **No daemon** — one blocking CLI call, all state on disk.

Status: **v0.9.0 — all 8 roadmap phases implemented.** Feature-complete;
pre-1.0 pending real-world validation (see [caveats](#honest-caveats)).

| command | what |
|---|---|
| `hydra doctor` | hardware → agent ceiling |
| `hydra plan <tasks.toml>` | file-independence proof → parallel/sequential batches + token projection, nothing dispatched |
| `hydra dispatch <task> <file>` | run ONE task end to end |
| `hydra run <file>` | run every task: parallel dispatch (governor-capped), per-task worktree, `.hydra/runs/<id>/` state |
| `hydra run --from-overpower` | read `.overpower/plan.md` as the task list |
| `hydra run --remote <host>` | rsync to a bigger box, run there, fetch the branches back |
| `hydra status` / `hydra resume` | run state table / retry failed + continue |
| `hydra merge` | review-gate each diff, merge in dependency order into `hydra/run-<id>` (your branch untouched) |
| `hydra context [query]` | show / FTS-search a run's shared memory |
| `hydra roles` | list agent roles (architect / coder / tester / reviewer / docs) |
| `hydra reflect` | distil recurring run failures into `.hydra/roles/<role>.lessons.md` |
| `hydra serve` | stdio MCP server — let an agent drive hydra |

A task sets `role`, `files`, `depends_on`. Each agent gets the run's shared
memory injected and writes its own entry back. `hydra.toml` configures the
agent, model routing, a token budget, review mode, and a path policy. Lifecycle
hooks live in `.hydra/hooks/`.

## Honest caveats

- **SWE-bench-Verified is a stub** — needs Docker + the dataset. `eval/` ships a
  real self-contained case and the harness; no SWE-bench number is claimed.
- **`--remote` is untested against a real host** — command construction is
  unit-tested; the ssh/rsync round-trip has not run end to end.
- **Dependent tasks build to an interface, not live code** — a task's worktree
  is cut from `base`, not from its merged dependencies. Keep interfaces explicit
  in prompts; shared memory carries the rest.
- **On a 2-core / low-RAM box the governor caps concurrency to 1** — hydra runs
  effectively sequential there. Real parallelism wants `--remote` to a bigger box.

```
$ hydra run tasks.toml
run 20260910-203432 — 3 task(s), base HEAD, governor allows 1
batch 0: conf, slug  (1 at a time)
  ✓ conf  (1 files, 0s)
  ✓ slug  (1 files, 0s)
batch 1: api  (1 at a time)
  ✓ api  (1 files, 0s)
  → 3 done · 0 failed · 0 skipped · 0 pending
```

```
$ hydra plan examples/tasks.toml
  4 task(s), 2 batch(es), governor allows 1 concurrent
  batch 0  [parallel x2 (governor runs 1 at a time)]
    - config: Add a config loader
    - slug: Add a slugify() helper
  batch 1  [parallel x2 (governor runs 1 at a time)]
    - api: Wire the HTTP endpoint
    - docs: Document the endpoint
  critical path ~41,394 tokens — parallelism available but governor caps to 1 — no speedup here
```

## Install

```
pip install -e .        # or: pipx install hydra-orchestrator (once published)
python -m pytest -q     # 82 tests
python eval/run_eval.py # the eval harness
```

## Design principles

1. **No daemon** — state on disk, not in a process.
2. **stdlib core** — Python 3.12+, `subprocess` + `git` + `sqlite3`.
3. **Concurrency = hardware, not ambition** — the governor is authoritative.
4. **Isolation over coordination** — worktrees + a file-independence proof, not consensus protocols.
5. **The human owns the merge** — conflicts and gate failures stop the run.

## License

MIT
