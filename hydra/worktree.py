"""One git worktree per task — isolation instead of coordination (principle C4).

Worktrees live under `<repo>/.hydra/wt/<task-id>` on a branch `hydra/<task-id>`
cut from the run's base. hydra writes `<repo>/.hydra/.gitignore` so the
worktrees and run logs never end up staged in the target repo.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import gitutil
from .errors import HydraError

_HYDRA_GITIGNORE = "wt/\nruns/\n"


@dataclass
class Worktree:
    path: Path
    branch: str
    task_id: str
    base: str


def _ensure_hydra_dir(root: Path) -> Path:
    hd = root / ".hydra"
    (hd / "wt").mkdir(parents=True, exist_ok=True)
    gi = hd / ".gitignore"
    if not gi.exists():
        gi.write_text(_HYDRA_GITIGNORE, encoding="utf-8")
    return hd


def create(root: str | Path, task_id: str, base: str) -> Worktree:
    root = Path(root)
    if not gitutil.has_commits(root):
        raise HydraError(f"{root} has no commits — hydra needs a base commit to branch from")
    _ensure_hydra_dir(root)
    wt_path = root / ".hydra" / "wt" / task_id
    branch = f"hydra/{task_id}"

    if wt_path.exists():
        remove(root, task_id)

    # delete a stale branch of the same name, then add fresh
    gitutil.git(["branch", "-D", branch], cwd=root, check=False)
    gitutil.git(["worktree", "add", "-b", branch, str(wt_path), base], cwd=root)
    return Worktree(path=wt_path, branch=branch, task_id=task_id, base=base)


def remove(root: str | Path, task_id: str) -> None:
    root = Path(root)
    wt_path = root / ".hydra" / "wt" / task_id
    gitutil.git(["worktree", "remove", "--force", str(wt_path)], cwd=root, check=False)
    gitutil.git(["branch", "-D", f"hydra/{task_id}"], cwd=root, check=False)
    gitutil.git(["worktree", "prune"], cwd=root, check=False)


def _stage_agent_work(wt: Worktree) -> None:
    """Stage everything the agent changed EXCEPT hydra's own `.hydra/` metadata
    (notes.md, run state, worktrees) — that is not the task's work product and
    would trip the review gate's scope check."""
    gitutil.git(["add", "-A"], cwd=wt.path)
    gitutil.git(["reset", "-q", "--", ".hydra"], cwd=wt.path, check=False)


def capture_diff(wt: Worktree) -> str:
    """All changes the agent made in the worktree, new files included,
    excluding `.hydra/`."""
    _stage_agent_work(wt)
    return gitutil.git(["diff", "--cached", "HEAD"], cwd=wt.path, check=False)


def commit(wt: Worktree, message: str) -> bool:
    """Commit the agent's staged changes onto the task branch. False if nothing
    to commit."""
    _stage_agent_work(wt)
    if not gitutil.git(["diff", "--cached", "--name-only"], cwd=wt.path).strip():
        return False
    gitutil.git(["-c", "user.name=hydra", "-c", "user.email=hydra@localhost",
                 "commit", "-q", "-m", message], cwd=wt.path)
    return True
