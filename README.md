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

Status: **pre-alpha, Phase 1 done** (of 8). Working: `hydra doctor` (hardware →
agent ceiling) and `hydra plan` (task file → parallel/sequential batches +
token projection, nothing dispatched). See [ROADMAP.md](ROADMAP.md).

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

## Install (once there's something to run)

```
pipx install hydra-orchestrator     # or: pip install -e .
```

## Usage (target shape)

```
hydra plan                 # dry-run: parallel-vs-sequential split + cost projection
hydra run                  # execute: worktree per task, dispatch, gate, merge
hydra run --remote <host>  # offload the swarm to a bigger box
hydra status               # live run state
hydra resume <run-id>      # continue from the last completed gate
hydra reflect              # distil recurring corrections into role lessons
hydra serve                # MCP server — let an agent drive hydra
```

## Design principles

1. **No daemon** — state on disk, not in a process.
2. **stdlib core** — Python 3.12+, `subprocess` + `git` + `sqlite3`.
3. **Concurrency = hardware, not ambition** — the governor is authoritative.
4. **Isolation over coordination** — worktrees + a file-independence proof, not consensus protocols.
5. **The human owns the merge** — conflicts and gate failures stop the run.

## License

MIT
