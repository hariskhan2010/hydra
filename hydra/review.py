"""The review gate — every task's diff is checked before it can be merged.

`rule` mode (default, zero tokens) is the important one: it verifies the agent
honoured the file contract the independence proof relied on. If a task edited a
file outside its declared touch-set, a parallel task may have edited the same
file — so that diff does not get merged without a human looking.

`agent` mode additionally asks the configured driver to PASS/FAIL the diff.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .drivers import Driver
from .independence import specs_overlap
from .tasks import Task

_SECRET_PATTERNS = [
    r"AKIA[0-9A-Z]{16}",                      # AWS access key id
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][A-Za-z0-9/\+_-]{16,}['\"]",
]
_BIG_HUNK_LINES = 800


def files_in_diff(diff: str) -> list[str]:
    out = []
    for ln in diff.splitlines():
        m = re.match(r"diff --git a/(.+?) b/(.+)$", ln)
        if m:
            out.append(m.group(2))
    return out


@dataclass
class ReviewResult:
    task_id: str
    passed: bool
    findings: list[str] = field(default_factory=list)


def review_diff(task: Task, diff: str, *, mode: str = "rule",
                driver: Driver | None = None, timeout: int = 300) -> ReviewResult:
    findings: list[str] = []

    if not diff.strip():
        findings.append("empty diff — nothing to merge")

    changed = files_in_diff(diff)
    if task.files:
        for f in changed:
            if not any(specs_overlap(f, d) for d in task.files):
                findings.append(
                    f"scope breach: touched {f!r}, not in declared files {list(task.files)} "
                    f"— a parallel task may own it")

    for pat in _SECRET_PATTERNS:
        if re.search(pat, diff):
            findings.append("possible secret in the diff")
            break

    added = sum(1 for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++"))
    if added > _BIG_HUNK_LINES:
        findings.append(f"large diff: +{added} lines — worth a manual look")

    if mode == "agent" and driver is not None and driver.available():
        verdict = _agent_review(task, diff, driver, timeout)
        if verdict and not verdict.upper().startswith("PASS"):
            findings.append(f"agent reviewer: {verdict}")

    return ReviewResult(task_id=task.id, passed=not findings, findings=findings)


def _agent_review(task: Task, diff: str, driver: Driver, timeout: int) -> str | None:
    prompt = (
        "You are a code reviewer. Reply on ONE line: 'PASS' if this diff correctly "
        f"and safely implements the task, or 'FAIL: <reason>' if not.\n\n"
        f"TASK: {task.title}\n{task.prompt}\n\nDIFF:\n{diff[:12000]}\n"
    )
    res = driver.run(prompt, ".", timeout)
    if not res.ok:
        return None
    return (res.stdout or "").strip().splitlines()[0] if res.stdout.strip() else None
