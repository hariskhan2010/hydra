"""Single-task dispatch (Phase 2): worktree -> agent -> diff.

No merge, no review gate yet (Phases 5). This is the unit that Phase 3
parallelises.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import worktree
from .drivers import Driver, DriverResult
from .tasks import Task


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


def dispatch_one(root: str | Path, task: Task, driver: Driver, *,
                 base: str = "HEAD", timeout: int = 900,
                 keep_worktree: bool = False) -> TaskResult:
    root = Path(root)
    wt = worktree.create(root, task.id, base)
    dr = driver.run(_prompt_for(task), str(wt.path), timeout)

    diff = ""
    error = dr.error
    if dr.ok:
        diff = worktree.capture_diff(wt)
        if not diff.strip():
            error = "agent exited cleanly but changed no files"

    ok = dr.ok and bool(diff.strip())
    result = TaskResult(
        task_id=task.id, ok=ok, diff=diff, driver=dr,
        worktree_path=wt.path if keep_worktree else None,
        branch=wt.branch if keep_worktree else None,
        error=None if ok else error,
    )
    if not keep_worktree:
        worktree.remove(root, task.id)
    return result


def _prompt_for(task: Task) -> str:
    files = ("\nFiles you are expected to create or modify:\n"
             + "\n".join(f"  - {f}" for f in task.files)) if task.files else ""
    return (
        f"# Task: {task.title}\n\n"
        f"{task.prompt}\n"
        f"{files}\n\n"
        "Work only within this directory. Make the change and stop — do not "
        "commit, push, or open a PR."
    )
