"""overpower integration (B10).

overpower (the user's build-methodology plugin) writes a plan to
`.overpower/plan.md` as `## Task N — <title>` sections. This reads that plan
into hydra Tasks so `hydra run` can parallelise an overpower plan directly:

    hydra run --from-overpower

Best-effort parser: each `## Task N — Title` (or `### Task ...`) starts a task;
a `Files:` / `Touches:` line or a bullet list of paths under it becomes `files`;
`Depends on: T1, T2` / `After: ...` becomes `depends_on`; a `Design:` or the
prose under the heading becomes the prompt.
"""
from __future__ import annotations

import re
from pathlib import Path

from .errors import HydraError
from .tasks import Task

_HEADING = re.compile(r"^#{2,4}\s+Task\s+(\S+?)\s*[—:-]\s*(.+?)\s*$", re.M)
# [^\S\n]* = spaces/tabs but not newlines, so a bare "Files:" doesn't slurp the
# next line's bullet.
_FILES_LINE = re.compile(r"^[^\S\n]*(?:files?|touches?)[^\S\n]*:[^\S\n]*(.+)$", re.I | re.M)
_DEPS_LINE = re.compile(r"^[^\S\n]*(?:depends?[^\S\n]*on|after)[^\S\n]*:[^\S\n]*(.+)$", re.I | re.M)
_BULLET_PATH = re.compile(r"^[^\S\n]*[-*]\s+`?([\w./-]+\.[\w]+)`?[^\S\n]*$", re.M)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "task"


def tasks_from_overpower(root: str | Path) -> list[Task]:
    root = Path(root)
    plan = root / ".overpower" / "plan.md"
    if not plan.exists():
        plan = root / ".overpower" / "progress.md"
    if not plan.exists():
        raise HydraError("no .overpower/plan.md or .overpower/progress.md found")

    text = plan.read_text(encoding="utf-8")
    marks = list(_HEADING.finditer(text))
    if not marks:
        raise HydraError(f"{plan}: no '## Task N — title' headings found")

    tasks: list[Task] = []
    id_by_num: dict[str, str] = {}
    for i, m in enumerate(marks):
        num, title = m.group(1), m.group(2).strip()
        body = text[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(text)]
        tid = _slug(title)
        base_tid, n = tid, 2
        while tid in id_by_num.values():
            tid, n = f"{base_tid}-{n}", n + 1
        id_by_num[num] = tid
        id_by_num[f"T{num}"] = tid
        id_by_num[f"Task {num}"] = tid

        files: list[str] = []
        fl = _FILES_LINE.search(body)
        if fl:
            files = [p.strip().strip("`") for p in re.split(r"[,\s]+", fl.group(1)) if p.strip()]
        files += [p for p in _BULLET_PATH.findall(body) if p not in files]

        deps_raw: list[str] = []
        dl = _DEPS_LINE.search(body)
        if dl:
            deps_raw = [d.strip() for d in re.split(r"[,\s]+", dl.group(1)) if d.strip()]

        prompt = re.sub(r"^[^\S\n]*(?:files?|touches?|depends?[^\S\n]*on|after)[^\S\n]*:.*$",
                        "", body, flags=re.I | re.M).strip()
        tasks.append(Task(id=tid, title=title, prompt=prompt or title,
                          files=tuple(files), depends_on=tuple(deps_raw)))

    # resolve dep references (T1 / 1 / "Task 1" / a slug) to task ids
    resolved: list[Task] = []
    for t in tasks:
        deps = []
        for d in t.depends_on:
            deps.append(id_by_num.get(d) or id_by_num.get(f"T{d}") or d)
        resolved.append(Task(id=t.id, title=t.title, prompt=t.prompt,
                             files=t.files, depends_on=tuple(dict.fromkeys(deps)),
                             role=t.role))
    return resolved
