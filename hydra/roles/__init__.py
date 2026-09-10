"""Role prompt fragments prepended to a task's prompt.

Built-ins ship in this package (`architect`, `coder`, `tester`, `reviewer`,
`docs`). A repo can override or add its own in `<repo>/.hydra/roles/<name>.md`.
"""
from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from ..errors import HydraError

BUILTIN = ("architect", "coder", "tester", "reviewer", "docs")


def load_role(root: str | Path, name: str) -> str:
    name = name.strip().lower()
    override = Path(root) / ".hydra" / "roles" / f"{name}.md"
    lessons = Path(root) / ".hydra" / "roles" / f"{name}.lessons.md"

    base: str | None = None
    if override.exists():
        base = override.read_text(encoding="utf-8").strip()
    else:
        try:
            res = files(__package__) / f"{name}.md"
            if res.is_file():
                base = res.read_text(encoding="utf-8").strip()
        except (FileNotFoundError, ModuleNotFoundError):
            base = None
    if base is None:
        raise HydraError(
            f"unknown role {name!r} — built-ins: {', '.join(BUILTIN)}; "
            f"or add .hydra/roles/{name}.md")

    if lessons.exists():
        base += "\n\n" + lessons.read_text(encoding="utf-8").strip()
    return base
