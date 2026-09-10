"""`hydra run` — execute a whole task file.

Batches come from the independence proof (hydra.independence). Within a batch,
worktrees are created serially, agents run in parallel up to the governor's
ceiling, then diffs are captured serially. Batches run in order.

A failure blocks its dependents (they are `skipped`) and stops the run after the
current batch — the human owns the recovery (principle C5). `hydra resume`
continues from the recorded state. No merge here (Phase 5).
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from . import dispatch, estimate, gitutil, governor
from .config import Config
from .drivers import Driver
from .independence import plan_waves
from .runstate import DONE, FAILED, PENDING, RUNNING, SKIPPED, RunState
from .tasks import Task, load_tasks


@dataclass
class RunOutcome:
    state: RunState
    stopped_early: bool
    dispatched: int
    failed: int
    skipped: int


def _blocked_by_failures(tasks: dict[str, Task], failed: set[str]) -> set[str]:
    """Every task with a failed ancestor in its depends_on closure."""
    blocked: set[str] = set()
    changed = True
    bad = set(failed)
    while changed:
        changed = False
        for t in tasks.values():
            if t.id in bad:
                continue
            if any(d in bad for d in t.depends_on):
                bad.add(t.id)
                blocked.add(t.id)
                changed = True
    return blocked


def run(root: str | Path, task_file: str | Path, cfg: Config, driver: Driver, *,
        max_agents: int | None = None, base: str | None = None,
        resume: bool = False, resume_id: str | None = None, on_event=None) -> RunOutcome:
    root = gitutil.repo_root(root)
    all_tasks = load_tasks(task_file)
    by_id = {t.id: t for t in all_tasks}
    base = base or cfg.base_branch
    budget = governor.compute(configured_max=max_agents)

    def emit(msg: str) -> None:
        if on_event:
            on_event(msg)

    if resume:
        state = RunState.load(root, resume_id)
        state.reset_unfinished()
        state.finished = None
        state.save(root)
        emit(f"resuming run {state.run_id} — {len(state.done_ids)} task(s) already done, "
             f"retrying {len(state.pending_ids)}")
    else:
        state = RunState.new(root, task_file, base, [t.id for t in all_tasks])
        emit(f"run {state.run_id} — {len(all_tasks)} task(s), base {base}, "
             f"governor allows {budget.max_agents}")

    remaining = [by_id[i] for i in state.pending_ids]
    if not remaining:
        emit("nothing to do — all tasks already done")
        return RunOutcome(state, False, 0, 0, 0)

    wp = plan_waves(remaining, satisfied=state.done_ids)
    dispatched = failed = skipped = 0
    stderr_tails: dict[str, str] = {}
    stop = False

    spent_tokens = 0
    for b in wp.batches:
        if stop:
            for tid in b.task_ids:
                state.tasks[tid].status = SKIPPED
                state.tasks[tid].note = "run stopped after an earlier failure"
            skipped += len(b.task_ids)
            continue

        batch_est = sum(estimate.estimate_task(by_id[i]).total for i in b.task_ids)
        if cfg.budget_tokens and spent_tokens + batch_est > cfg.budget_tokens:
            emit(f"cost ceiling: ~{spent_tokens:,} spent, batch {b.index} would add "
                 f"~{batch_est:,}, limit is {cfg.budget_tokens:,} — stopping")
            for tid in b.task_ids:
                state.tasks[tid].status = SKIPPED
                state.tasks[tid].note = "skipped — token budget reached"
            skipped += len(b.task_ids)
            stop = True
            continue
        spent_tokens += batch_est

        batch_tasks = [by_id[i] for i in b.task_ids]
        for t in batch_tasks:
            state.tasks[t.id].status = RUNNING
            state.tasks[t.id].batch = b.index
        state.save(root)
        conc = max(1, min(len(batch_tasks), budget.max_agents))
        emit(f"batch {b.index}: {', '.join(b.task_ids)}  ({conc} at a time)")

        wts = {t.id: dispatch.prepare(root, t, base) for t in batch_tasks}
        drv_results = {}
        with ThreadPoolExecutor(max_workers=conc) as ex:
            futs = {ex.submit(dispatch.run_agent, wts[t.id], t, driver, cfg.timeout): t
                    for t in batch_tasks}
            for fut in futs:
                t = futs[fut]
                drv_results[t.id] = fut.result()

        for t in batch_tasks:
            res = dispatch.finalize(root, t, wts[t.id], drv_results[t.id], keep_worktree=True)
            ts = state.tasks[t.id]
            ts.branch = res.branch
            ts.files_changed = res.files_changed
            ts.duration_s = round(res.driver.duration_s, 1)
            dispatched += 1
            if res.ok:
                ts.status = DONE
                state.write_diff(root, t.id, res.diff)
                emit(f"  ✓ {t.id}  ({res.files_changed} files, {ts.duration_s:.0f}s)")
            else:
                ts.status = FAILED
                ts.error = res.error
                failed += 1
                stderr_tails[t.id] = res.driver.stderr
                emit(f"  ✗ {t.id}  — {res.error}")
        state.save(root)

        if state.any_failed:
            failed_ids = {t.id for t in state.tasks.values() if t.status == FAILED}
            for tid in _blocked_by_failures(by_id, failed_ids):
                if state.tasks[tid].status in (RUNNING, PENDING):
                    state.tasks[tid].status = SKIPPED
                    state.tasks[tid].note = "depends on a failed task"
                    skipped += 1
            stop = True

    state.finished = time.strftime("%Y-%m-%d %H:%M:%S")
    state.save(root)
    fpath = state.write_failures(root, stderr_tails)
    if fpath:
        emit(f"failures written to {fpath}")
    return RunOutcome(state, stop, dispatched, failed, skipped)
