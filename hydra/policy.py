"""Policy engine (A12) — small, I/O-bound, enforced in-process (no WASM).

    [policy]
    allowed_paths      = ["src/**", "tests/**", "docs/**"]
    forbidden_paths    = [".github/**", "infra/**", "*.lock"]
    max_files_per_task = 8

Checked before anything is dispatched (a violation stops the run for free) and
again against each real diff at merge time.
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field

from .tasks import Task


@dataclass
class Policy:
    allowed_paths: list[str] = field(default_factory=list)
    forbidden_paths: list[str] = field(default_factory=list)
    max_files_per_task: int | None = None

    @property
    def active(self) -> bool:
        return bool(self.allowed_paths or self.forbidden_paths or self.max_files_per_task)


def _matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        base = pattern[:-3]
        return path == base or path.startswith(base + "/")
    return fnmatch.fnmatch(path, pattern)


def _path_ok(path: str, pol: Policy) -> str | None:
    for f in pol.forbidden_paths:
        if _matches(path, f):
            return f"{path!r} matches forbidden_paths {f!r}"
    if pol.allowed_paths and not any(_matches(path, a) for a in pol.allowed_paths):
        return f"{path!r} is outside allowed_paths"
    return None


def check_declared(tasks: list[Task], pol: Policy) -> list[str]:
    if not pol.active:
        return []
    out: list[str] = []
    for t in tasks:
        if pol.max_files_per_task and len(t.files) > pol.max_files_per_task:
            out.append(f"task {t.id!r}: declares {len(t.files)} files "
                       f"(max_files_per_task = {pol.max_files_per_task})")
        for f in t.files:
            v = _path_ok(f, pol)
            if v:
                out.append(f"task {t.id!r}: {v}")
    return out


def check_diff_paths(task_id: str, changed: list[str], pol: Policy) -> list[str]:
    if not pol.active:
        return []
    out = []
    for f in changed:
        v = _path_ok(f, pol)
        if v:
            out.append(f"task {task_id!r} diff: {v}")
    return out
