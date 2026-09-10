"""Thin wrappers over the `git` CLI. No GitPython dependency (principle C2)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from .errors import HydraError


def git(args: list[str], cwd: str | Path, *, check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=str(cwd),
                       capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode != 0:
        raise HydraError(f"git {' '.join(args)} failed: {(r.stderr or r.stdout).strip()}")
    return r.stdout


def repo_root(path: str | Path = ".") -> Path:
    try:
        out = git(["rev-parse", "--show-toplevel"], cwd=path)
    except HydraError:
        raise HydraError(f"{Path(path).resolve()} is not inside a git repository")
    return Path(out.strip())


def current_branch(root: str | Path) -> str:
    return git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=root).strip()


def has_commits(root: str | Path) -> bool:
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(root), capture_output=True)
    return r.returncode == 0


def is_clean(root: str | Path) -> bool:
    return git(["status", "--porcelain"], cwd=root).strip() == ""
