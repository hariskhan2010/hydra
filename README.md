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

Status: **pre-alpha, Phase 0.** Scaffold only. See [ROADMAP.md](ROADMAP.md) for
the full feature spec and the phase plan.

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
