---
name: using-hydra
description: Use when a plan has two or more tasks that touch disjoint files and could be built in parallel by separate agents. Runs them concurrently in isolated worktrees, then review-gates and merges.
---

# Using hydra

hydra runs several coding-agent sessions in parallel across git worktrees, then
reviews and merges. Use it once you have a plan with **independent** tasks.

## When to reach for it

- The plan has ≥2 tasks whose declared file sets don't overlap and that don't
  depend on each other.
- Each task is self-contained enough to hand to a fresh agent with just a prompt
  and a file list.

If the tasks are tightly coupled or share files, don't — run them in sequence.

## From an overpower plan

```
hydra run --from-overpower
```

Reads `.overpower/plan.md` (`## Task N — title` sections, `Files:` lines,
`Depends on:` lines) as the task list. Then:

```
hydra plan   --from-overpower     # see the parallel/sequential split + cost first
hydra run    --from-overpower     # execute
hydra status                      # progress
hydra merge                       # review-gate + merge into hydra/run-<id>
git merge hydra/run-<id>          # you do the final merge
```

## From a task file

`tasks.toml`:

```toml
[[task]]
id = "slug"
title = "slugify helper"
prompt = "Implement slugify(s) in src/slug.py with tests."
files = ["src/slug.py", "tests/test_slug.py"]
role = "coder"
```

## What hydra guarantees

- Parallel **only** on tasks with provably-disjoint files; everything else runs
  in order.
- Concurrency capped to the machine (`hydra doctor` shows the ceiling).
- Every failure surfaced in `FAILURES.md`; `hydra resume` continues.
- Your real branch is never touched — output lands on `hydra/run-<id>`.

## What it does NOT do

- It won't split a task for you. You write the plan.
- Dependent tasks are built to the interface in shared memory, not against each
  other's live code — keep interfaces explicit in the prompts.
