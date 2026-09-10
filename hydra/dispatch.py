"""Task dispatch: worktree -> agent -> diff.

`dispatch_one` is the single-task path (`hydra dispatch`). The runner (Phase 3)
uses the three pieces — `prepare`, `run_agent`, `finalize` — so it can create
worktrees serially, run agents in parallel, then capture diffs serially.

No merge, no review gate here (Phase 5).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import worktree
from .drivers import Driver, DriverResult
from .tasks import Task
from .worktree import Worktree


@dataclass
class TaskResult:
    task_id: str
    ok: bool
    diff: str
    driver: DriverResult
    worktree_path: Path | None
    branch: str | None
    error: str | None

    @property
    def files_changed(self) -> int:
        return sum(1 for ln in self.diff.splitlines() if ln.startswith("diff --git "))


def prompt_for(task: Task, *, role_text: str = "", context_text: str = "") -> str:
    files = ("\nFiles you are expected to create or modify:\n"
             + "\n".join(f"  - {f}" for f in task.files)) if task.files else ""
    parts: list[str] = []
    if role_text.strip():
        parts.append(role_text.strip())
    if context_text.strip():
        parts.append("# What earlier tasks in this run produced\n\n"
                     + context_text.strip()
                     + "\n\n(You cannot see their code directly — build to the "
                       "interfaces described above.)")
    parts.append(f"# Task: {task.title}\n\n{task.prompt}\n{files}")
    parts.append("Work only within this directory. Make the change and stop — do "
                 "not commit, push, or open a PR. Optional: leave a short note "
                 "for later tasks in `.hydra/notes.md`.")
    return "\n\n".join(parts)


def prepare(root: str | Path, task: Task, base: str) -> Worktree:
    return worktree.create(root, task.id, base)


def run_agent(wt: Worktree, task: Task, driver: Driver, timeout: int, *,
              role_text: str = "", context_text: str = "",
              model: str | None = None) -> DriverResult:
    return driver.run(prompt_for(task, role_text=role_text, context_text=context_text),
                      str(wt.path), timeout, model=model)


def finalize(root: str | Path, task: Task, wt: Worktree, dr: DriverResult, *,
             keep_worktree: bool) -> TaskResult:
    diff = ""
    error = dr.error
    if dr.ok:
        diff = worktree.capture_diff(wt)
        if not diff.strip():
            error = "agent exited cleanly but changed no files"
    ok = dr.ok and bool(diff.strip())
    if ok:
        # commit onto the task branch so it can be merged later (Phase 5)
        worktree.commit(wt, f"hydra: {task.id} — {task.title}")
    res = TaskResult(
        task_id=task.id, ok=ok, diff=diff, driver=dr,
        worktree_path=wt.path if keep_worktree else None,
        branch=wt.branch if keep_worktree else None,
        error=None if ok else error,
    )
    if not keep_worktree:
        worktree.remove(root, task.id)
    return res


def dispatch_one(root: str | Path, task: Task, driver: Driver, *,
                 base: str = "HEAD", timeout: int = 900,
                 keep_worktree: bool = False) -> TaskResult:
    wt = prepare(root, task, base)
    dr = run_agent(wt, task, driver, timeout)
    return finalize(root, task, wt, dr, keep_worktree=keep_worktree)
