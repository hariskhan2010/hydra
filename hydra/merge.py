"""Phase 5 — review-gate each task's diff, then merge in dependency order.

All task branches are merged into an integration branch `hydra/run-<id>` in a
dedicated worktree at `.hydra/integration`. The result is a branch for the human
to review and merge into their real branch — hydra never touches the target
branch itself (principle C5). A merge conflict or a failed review stops the
process and is reported.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import gitutil, review, worktree
from .drivers import Driver
from .errors import HydraError
from .independence import _dependency_layers
from .runstate import DONE, RunState
from .tasks import Task


@dataclass
class MergeOutcome:
    integration_branch: str
    merged: list[str] = field(default_factory=list)
    blocked: list[tuple[str, list[str]]] = field(default_factory=list)  # (task, reasons)
    conflicted: str | None = None

    @property
    def ok(self) -> bool:
        return not self.blocked and self.conflicted is None


def _merge_order(tasks: list[Task]) -> list[str]:
    return [tid for layer in _dependency_layers(tasks, set()) for tid in layer]


def merge_run(root: str | Path, state: RunState, tasks_by_id: dict[str, Task], *,
              review_mode: str = "rule", driver: Driver | None = None,
              on_event=None) -> MergeOutcome:
    root = gitutil.repo_root(root)
    emit = on_event or (lambda _m: None)

    done = [tasks_by_id[t.id] for t in state.tasks.values()
            if t.status == DONE and t.id in tasks_by_id]
    if not done:
        raise HydraError("no completed tasks to merge")

    integ_branch = f"hydra/run-{state.run_id}"
    integ_wt = root / ".hydra" / "integration"
    if integ_wt.exists():
        gitutil.git(["worktree", "remove", "--force", str(integ_wt)], cwd=root, check=False)
    gitutil.git(["branch", "-D", integ_branch], cwd=root, check=False)
    gitutil.git(["worktree", "add", "-b", integ_branch, str(integ_wt), state.base], cwd=root)

    out = MergeOutcome(integration_branch=integ_branch)
    try:
        for tid in _merge_order(done):
            task = tasks_by_id[tid]
            diff = state.diff_path(root, tid).read_text(encoding="utf-8") \
                if state.diff_path(root, tid).exists() else ""

            rr = review.review_diff(task, diff, mode=review_mode, driver=driver)
            if not rr.passed:
                out.blocked.append((tid, rr.findings))
                emit(f"  ✗ {tid} blocked by review: {'; '.join(rr.findings)}")
                break
            emit(f"  ✓ {tid} passed review")

            m = gitutil.git(["merge", "--no-ff", "-m", f"hydra: {tid} — {task.title}",
                             f"hydra/{tid}"], cwd=integ_wt, check=False)
            if "CONFLICT" in m or "Automatic merge failed" in m:
                gitutil.git(["merge", "--abort"], cwd=integ_wt, check=False)
                out.conflicted = tid
                emit(f"  ✗ {tid}: merge conflict — stopped, nothing forced")
                break
            out.merged.append(tid)
            emit(f"  ✓ {tid} merged")
    finally:
        gitutil.git(["worktree", "remove", "--force", str(integ_wt)], cwd=root, check=False)

    return out
