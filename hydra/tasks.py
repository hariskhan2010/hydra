"""The task model and its loader.

A run is a list of tasks. Each task is a unit of work handed to one agent in
one worktree. The loader accepts a TOML file:

    [[task]]
    id = "slugify"
    title = "Add a slugify() helper"
    prompt = "Implement slugify(text) in src/text/slug.py with tests."
    files = ["src/text/slug.py", "tests/test_slug.py"]
    depends_on = []

`files` is the task's declared touch-set — the paths (or `dir/**` prefixes) the
agent is expected to create or modify. It drives the independence proof
(hydra.independence). Be honest here: understating it causes merge conflicts,
overstating it just serialises more than necessary.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .errors import HydraError

_ALLOWED_KEYS = {"id", "title", "prompt", "files", "depends_on"}


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    prompt: str
    files: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()


def _norm(spec: str) -> str:
    return spec.replace("\\", "/").strip().lstrip("./")


def load_tasks(path: str | Path) -> list[Task]:
    p = Path(path)
    if not p.exists():
        raise HydraError(f"task file not found: {p}")
    try:
        data = tomllib.loads(p.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise HydraError(f"{p}: invalid TOML — {e}") from e

    raw = data.get("task")
    if not isinstance(raw, list) or not raw:
        raise HydraError(f"{p}: no [[task]] entries")

    tasks: list[Task] = []
    seen: set[str] = set()
    for i, entry in enumerate(raw, 1):
        if not isinstance(entry, dict):
            raise HydraError(f"{p}: [[task]] #{i} is not a table")
        extra = set(entry) - _ALLOWED_KEYS
        if extra:
            raise HydraError(f"{p}: [[task]] #{i} has unknown key(s): {sorted(extra)}")
        for req in ("id", "title", "prompt"):
            if not entry.get(req) or not str(entry[req]).strip():
                raise HydraError(f"{p}: [[task]] #{i} is missing '{req}'")
        tid = str(entry["id"]).strip()
        if tid in seen:
            raise HydraError(f"{p}: duplicate task id {tid!r}")
        seen.add(tid)

        files = tuple(_norm(str(x)) for x in entry.get("files", []) if str(x).strip())
        deps = tuple(str(x).strip() for x in entry.get("depends_on", []) if str(x).strip())
        tasks.append(Task(id=tid, title=str(entry["title"]).strip(),
                          prompt=str(entry["prompt"]).strip(),
                          files=files, depends_on=deps))

    ids = {t.id for t in tasks}
    for t in tasks:
        for d in t.depends_on:
            if d not in ids:
                raise HydraError(f"task {t.id!r} depends on unknown task {d!r}")
            if d == t.id:
                raise HydraError(f"task {t.id!r} depends on itself")
    return tasks
