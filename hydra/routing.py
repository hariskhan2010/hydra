"""Model routing (A8) — cheap model for throwaway work, capable model for edits.

    [routing]
    default   = "claude-sonnet-5"
    plan      = "claude-haiku-4-5"
    review    = "deepseek-v4-flash"
    architect = "claude-sonnet-5"
    coder     = "claude-sonnet-5"
    docs      = "claude-haiku-4-5"

Keys are a task's `role` (or the special `default` / `plan` / `review`). The
value is passed to the driver as its model (`--model` for claude/qwen,
`{model}` substitution for a generic template).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .tasks import Task


@dataclass
class Routing:
    table: dict[str, str] = field(default_factory=dict)

    @property
    def active(self) -> bool:
        return bool(self.table)

    def model_for(self, task: Task) -> str | None:
        if task.role and task.role in self.table:
            return self.table[task.role]
        return self.table.get("default")

    def model_for_slot(self, slot: str) -> str | None:
        return self.table.get(slot) or self.table.get("default")
