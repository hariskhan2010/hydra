"""Persistent run state under `<repo>/.hydra/runs/<run-id>/` (principle B4).

    state.json          the whole run: tasks, statuses, timings, branches
    diffs/<task>.patch   captured diff per task that produced one
    FAILURES.md          human-readable, only written when something fails (B5)

State is plain JSON on disk — no daemon holds it. `hydra status` / `hydra resume`
just read it back.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .errors import HydraError

PENDING, RUNNING, DONE, FAILED, SKIPPED = "pending", "running", "done", "failed", "skipped"


@dataclass
class TaskState:
    id: str
    status: str = PENDING
    batch: int | None = None
    branch: str | None = None
    files_changed: int = 0
    duration_s: float = 0.0
    error: str | None = None
    note: str | None = None


@dataclass
class RunState:
    run_id: str
    task_file: str
    base: str
    created: str
    tasks: dict[str, TaskState] = field(default_factory=dict)
    finished: str | None = None

    # ---- disk -------------------------------------------------------------

    @staticmethod
    def _dir(root: Path, run_id: str) -> Path:
        return Path(root) / ".hydra" / "runs" / run_id

    @classmethod
    def new(cls, root: Path, task_file: str, base: str, task_ids: list[str]) -> "RunState":
        run_id = time.strftime("%Y%m%d-%H%M%S")
        d = cls._dir(root, run_id)
        if d.exists():
            run_id += "-" + str(int(time.time() * 1000) % 1000)
            d = cls._dir(root, run_id)
        (d / "diffs").mkdir(parents=True, exist_ok=True)
        rs = cls(run_id=run_id, task_file=str(task_file), base=base,
                 created=time.strftime("%Y-%m-%d %H:%M:%S"),
                 tasks={tid: TaskState(id=tid) for tid in task_ids})
        rs.save(root)
        return rs

    @classmethod
    def load(cls, root: Path, run_id: str | None) -> "RunState":
        runs_dir = Path(root) / ".hydra" / "runs"
        if run_id is None:
            candidates = sorted(p.name for p in runs_dir.glob("*") if p.is_dir()) if runs_dir.exists() else []
            if not candidates:
                raise HydraError("no runs found under .hydra/runs/")
            run_id = candidates[-1]
        f = cls._dir(root, run_id) / "state.json"
        if not f.exists():
            raise HydraError(f"no such run: {run_id}")
        raw = json.loads(f.read_text(encoding="utf-8"))
        raw["tasks"] = {k: TaskState(**v) for k, v in raw["tasks"].items()}
        return cls(**raw)

    def save(self, root: Path) -> None:
        d = self._dir(Path(root), self.run_id)
        d.mkdir(parents=True, exist_ok=True)
        payload = asdict(self)
        (d / "state.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def write_diff(self, root: Path, task_id: str, diff: str) -> None:
        if diff.strip():
            (self._dir(Path(root), self.run_id) / "diffs" / f"{task_id}.patch").write_text(
                diff, encoding="utf-8")

    def diff_path(self, root: Path, task_id: str) -> Path:
        return self._dir(Path(root), self.run_id) / "diffs" / f"{task_id}.patch"

    # ---- queries --------------------------------------------------------

    @property
    def pending_ids(self) -> list[str]:
        """Everything not yet DONE — retried on resume."""
        return [t.id for t in self.tasks.values() if t.status != DONE]

    def reset_unfinished(self) -> None:
        for t in self.tasks.values():
            if t.status != DONE:
                t.status = PENDING
                t.error = None
                t.note = None

    @property
    def any_failed(self) -> bool:
        return any(t.status == FAILED for t in self.tasks.values())

    @property
    def done_ids(self) -> set[str]:
        return {t.id for t in self.tasks.values() if t.status == DONE}

    # ---- FAILURES.md --------------------------------------------------

    def render_table(self) -> str:
        head = (f"run {self.run_id}  ({self.task_file}, base {self.base})"
                f"{'  — finished ' + self.finished if self.finished else '  — in progress'}")
        rows = [head]
        w = max((len(t.id) for t in self.tasks.values()), default=4)
        for t in self.tasks.values():
            fc = f"{t.files_changed} file(s)" if t.status == DONE else "—"
            extra = f"   {t.error or t.note}" if (t.error or t.note) else ""
            rows.append(f"  {t.id:<{w}}  {t.status:<8} {fc:<10} {t.branch or '—':<16}{extra}")
        done = sum(t.status == DONE for t in self.tasks.values())
        fail = sum(t.status == FAILED for t in self.tasks.values())
        skip = sum(t.status == SKIPPED for t in self.tasks.values())
        pend = sum(t.status in (PENDING, RUNNING) for t in self.tasks.values())
        rows.append(f"  → {done} done · {fail} failed · {skip} skipped · {pend} pending")
        return "\n".join(rows)

    def write_failures(self, root: Path, details: dict[str, str]) -> Path | None:
        failed = [t for t in self.tasks.values() if t.status in (FAILED, SKIPPED)]
        path = self._dir(Path(root), self.run_id) / "FAILURES.md"
        if not failed:
            if path.exists():
                path.unlink()
            return None
        lines = [f"# hydra run {self.run_id} — FAILURES", ""]
        for t in failed:
            where = f"batch {t.batch}" if t.batch is not None else "not started"
            lines.append(f"## task `{t.id}` ({where})")
            lines.append(f"- status: {t.status}")
            if t.error:
                lines.append(f"- error: {t.error}")
            if t.note:
                lines.append(f"- note: {t.note}")
            if t.branch:
                lines.append(f"- branch: {t.branch}  (worktree .hydra/wt/{t.id})")
            tail = details.get(t.id, "").strip()
            if tail:
                lines.append("- agent stderr (tail):")
                lines += [f"    {ln}" for ln in tail.splitlines()[-20:]]
            lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
