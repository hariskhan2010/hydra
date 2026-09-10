# hydra — roadmap

**Goal:** everything Ruflo (Claude Flow) does, plus what it doesn't. A
multi-agent orchestrator for coding-agent CLIs — parallel specialized agents,
shared memory, review gates, resumable state — that is **agent-agnostic**,
**git-native**, **hardware-adaptive**, and **honest about failure and cost**.

Ruflo is Claude-Code-only, token-hungry, complex, and its headline numbers are
self-reported. hydra keeps the real capabilities and fixes those four things.

---

## Part A — Ruflo feature parity

| # | Ruflo capability | hydra plan |
|---|---|---|
| A1 | **Multi-agent swarm** — specialized roles (architect, coder, tester, reviewer, analyst, …) | Role library as prompt files in `roles/`. Ship ~8 core roles; user adds more. No hard cap on *defined* roles, only on *concurrent* ones (see C3). |
| A2 | **Parallel execution** across agents | `git worktree` per task + `subprocess` per agent. Concurrency governed by the hardware governor (C3), not a fixed 54. |
| A3 | **Topologies** — mesh / hierarchical / ring / star | One real topology: **hierarchical** (an orchestrator fans out to workers, collects, merges). The others are renamed message-passing patterns with no benefit for a single-repo build; documented as out of scope with the reason. |
| A4 | **Consensus** — Raft / BFT / Gossip / CRDT | Replaced by **file-set independence proof** (B1). Consensus solves "distributed nodes disagree"; hydra has no distributed nodes. If two agents' outputs conflict, that's a merge conflict → surfaced to the human, never auto-voted. |
| A5 | **Shared / collective memory** | `.hydra/context.md` (append-only, git-tracked) + a SQLite FTS index. Every agent reads the current context at spawn and writes findings back at exit. This is Ruflo's best idea; hydra keeps it verbatim in spirit. |
| A6 | **Continuous learning** from agent outputs | `hydra reflect` — after a run, distils recurring corrections into `roles/<role>.lessons.md` that prepend to that role's next prompt. Explicit, inspectable, revertable — not a black-box weight update. |
| A7 | **SWE-bench harness** (Ruflo claims 84.8 %) | `eval/` — a real, reproducible harness on SWE-bench-Verified with a pinned adapter. We publish the script and the raw runs, not just a number. No claim ships until the harness does. |
| A8 | **Model routing / cost optimisation** (Ruflo claims 75 %) | `hydra.toml` routing table: `plan`/`review`/`summary` → cheap model, `implement` → capable model. Per-provider (Anthropic, OpenAI-compatible, Ollama, OpenRouter). Prints projected vs actual spend. |
| A9 | **Hooks integration** | Emits the standard hook events other tools consume; consumes a `.hydra/hooks/` dir of user scripts at each lifecycle point. |
| A10 | **MCP integration** | `hydra serve` — an MCP server exposing `dispatch`, `status`, `context`, `merge` so an agent can drive hydra. |
| A11 | **Session persistence / resume** | All run state in `.hydra/run-<id>/` (task states, worktree map, context, logs). `hydra resume <id>` continues from the last completed gate. |
| A12 | **Policy engine** (Ruflo: Rust→WASM) | `hydra.toml` `[policy]` — allowed paths, forbidden commands, max files per task, required gates. Enforced in-process (Python); a breach stops the run. No WASM. |

## Part B — what Ruflo doesn't have (our additions)

| # | Feature | Why it matters |
|---|---|---|
| B1 | **File-set independence proof** | Before parallelising, static-analyse each task's declared + inferred file touch-set. Parallel *only* on disjoint sets; everything else serialised. This is the safety story Ruflo fakes with "consensus". |
| B2 | **Agent-agnostic** | Drivers for `claude -p`, `qwen -p`, `codex`, `gemini`, any OpenAI-compatible `-p` CLI. One `[agent]` block in `hydra.toml`. Ruflo is Claude-only. |
| B3 | **Hardware governor** | Reads free RAM + core count at start; caps concurrency (`N = min(cores-1, free_gb // per_agent_gb, configured_max)`). On a 2-core/8 GB box → N=2, transparently. Never OOMs the machine. |
| B4 | **git-native state** | `.hydra/` is committed. Every run, every context update, every merge is a diff you can review in a PR and `git revert`. Ruflo's state is opaque. |
| B5 | **No silent failures** | Every gate failure, dropped task, or capture error is written to `.hydra/run-<id>/FAILURES.md` and echoed to stdout. A run never "quietly" produces less than asked. |
| B6 | **Plan / dry-run mode** | `hydra plan` shows the parallel-vs-sequential split, projected token cost, and the worktree layout — before spending a token. |
| B7 | **Hard cost ceiling** | `hydra.toml` `budget_usd` / `budget_tokens`. The orchestrator stops dispatching and surfaces partial results when the ceiling is hit. |
| B8 | **Remote offload** | `hydra run --remote <host>` rsyncs the repo to a bigger box, runs the swarm there, streams logs back, pulls the merged branch. The laptop stays the control plane; the cloud box does the parallel work. |
| B9 | **Honest benchmarking** | Every performance claim in the README links to a script in `eval/` and a raw results file. If it's not reproducible, it's not claimed. |
| B10 | **overpower integration** | Reads an `.overpower/` plan directly as the task list; ships a `using-hydra` skill. The two tools compose: overpower plans, hydra parallelises. |

## Part C — cross-cutting principles

- **C1 No daemon.** Every command is one blocking invocation. State on disk, not in a running process.
- **C2 Python 3.12+ stdlib core.** `subprocess` + `git` CLI + `sqlite3`. Optional extras only for embeddings.
- **C3 Concurrency = hardware, not ambition.** The governor (B3) is authoritative. `--max-agents` can only *lower* it.
- **C4 Isolation over coordination.** Worktrees + independence proof instead of message-passing consensus.
- **C5 Human owns the merge.** Conflicts and gate failures stop the run. hydra never force-resolves.

---

## Build phases

| Phase | Scope | Ships |
|---|---|---|
| **0** | Repo scaffold, `hydra` package, CLI skeleton, `hydra.toml` schema, this roadmap | `hydra --help`, `hydra --version` |
| **1** | Task model (`tasks.toml` / `.overpower` plan reader) · **file-set independence proof (B1)** · hardware governor (B3) · `hydra plan` (B6) | dry-run split + cost projection, no dispatch |
| **2** | Worktree manager · agent driver interface · **`claude -p` + `qwen -p` drivers (B2)** · single-task dispatch · diff capture | one task, end to end |
| **3** | Parallel dispatch (governor-capped) · `.hydra/run-<id>/` state (B4) · `hydra status` · `hydra resume` (A11) · `FAILURES.md` (B5) | **MVP — parallel execution** |
| **4** | Role library (A1) · shared memory `.hydra/context.md` + FTS (A5) · lifecycle hooks (A9) | specialised roles sharing context |
| **5** | Review gate per diff (reviewer role) · dependency-ordered merge · conflict surfacing (C5) · cost ceiling (B7) | plan → parallel build → review → merge |
| **6** | Model routing table (A8) · `hydra serve` MCP (A10) · policy engine (A12) · hooks-in (A9) | cost control + drivable by an agent |
| **7** | `hydra reflect` lessons (A6) · `eval/` SWE-bench harness (A7, B9) | learning loop + honest numbers |
| **8** | `hydra run --remote` offload (B8) · `using-hydra` skill + `.overpower` integration (B10) | laptop control plane, cloud muscle |

**MVP = phases 0–3.** Everything after is additive; each phase ships something usable.

---

## Explicitly out of scope (and why)

- **Raft/BFT/Gossip consensus** — solves disagreement between distributed replicas. hydra has one repo and one merge point. See A4 / B1.
- **Mesh/ring/star topologies** — message-passing patterns with no measured benefit on a single-repo build. Hierarchical (A3) covers the real case.
- **Rust/WASM policy engine** — the policy set is small and I/O-bound; Python enforces it fine. See A12.
- **Chasing a SWE-bench headline** — we run the harness and publish raw results (A7). The number is an output, not a goal.
