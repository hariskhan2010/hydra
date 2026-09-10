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
    if override.exists():
        return override.read_text(encoding="utf-8").strip()
    try:
        res = files(__package__) / f"{name}.md"
        if res.is_file():
            return res.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, ModuleNotFoundError):
        pass
    raise HydraError(
        f"unknown role {name!r} — built-ins: {', '.join(BUILTIN)}; "
        f"or add .hydra/roles/{name}.md")
