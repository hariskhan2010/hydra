"""Shared memory — Ruflo's best idea, kept (A5).

Each task's agent gets the run's accumulated context injected at spawn, and its
own entry appended when it finishes. Two artefacts in the run dir:

    context.md   append-only, human-readable
    context.db   SQLite FTS5, for `hydra context "<query>"`

An agent may also drop a free-text note in `.hydra/notes.md` inside its
worktree; hydra folds that into the entry.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


class SharedContext:
    def __init__(self, run_dir: str | Path):
        self.dir = Path(run_dir)
        self.md = self.dir / "context.md"
        self.db_path = self.dir / "context.db"
        self._db = sqlite3.connect(self.db_path)
        self._db.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS entries "
            "USING fts5(task_id, body, tokenize='porter unicode61')")
        self._db.commit()

    def append(self, task_id: str, summary: str, files: list[str], notes: str = "") -> None:
        block = [f"## {task_id}", summary.strip()]
        if files:
            block.append("files: " + ", ".join(files))
        if notes.strip():
            block.append("notes: " + notes.strip())
        text = "\n".join(block) + "\n\n"
        with self.md.open("a", encoding="utf-8") as fh:
            fh.write(text)
        self._db.execute("INSERT INTO entries(task_id, body) VALUES(?, ?)",
                         (task_id, text))
        self._db.commit()

    def current(self, limit_chars: int = 6000) -> str:
        if not self.md.exists():
            return ""
        text = self.md.read_text(encoding="utf-8")
        return text[-limit_chars:] if len(text) > limit_chars else text

    def search(self, query: str, k: int = 5) -> list[str]:
        try:
            rows = self._db.execute(
                "SELECT body FROM entries WHERE entries MATCH ? "
                "ORDER BY rank LIMIT ?", (query, k)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [r[0].strip() for r in rows]

    def close(self) -> None:
        self._db.close()


def read_agent_notes(worktree_path: str | Path) -> str:
    p = Path(worktree_path) / ".hydra" / "notes.md"
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return ""
