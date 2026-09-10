# hydra eval

**No performance number is published unless it came out of `run_eval.py`.**

```
python eval/run_eval.py            # all cases
python eval/run_eval.py two-helpers
```

Each `cases/<name>/` is:

| file | what |
|---|---|
| `case.toml` | `tasks = "..."`, `check = "<shell command>"` (exit 0 = pass) |
| `repo/` | seed files copied into a fresh `git init` repo |
| `tasks.toml` | the hydra task file |
| `hydra.toml` | optional — agent/routing/policy for the case |

The harness: build the temp repo → `hydra run tasks.toml` → `hydra merge` →
checkout the integration branch → run `check` → record pass/fail. Raw results
land in `results/<timestamp>.json` (git-ignored).

## Cases

- **two-helpers** — two independent helpers in one batch, a consumer that
  depends on both in the next. Exercises the independence proof, shared memory,
  and dependency-ordered merge end to end. `check` = the repo's pytest.

## SWE-bench-Verified — stub

The A7 goal is a reproducible run on SWE-bench-Verified. That needs Docker and
the ~7 GB dataset, which the current dev box ([2 cores / 7.6 GB](../ROADMAP.md))
can't run. The adapter shape is designed for it — a case is just a repo state +
a task + a check — but the SWE-bench loader is **not implemented**. Until it is,
hydra ships **no** SWE-bench number. This file is the honest placeholder.
