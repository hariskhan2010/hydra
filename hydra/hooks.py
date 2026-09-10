"""Lifecycle hooks (A9).

Drop an executable at `<repo>/.hydra/hooks/<event>` (a shell script, a `.py`,
anything with a shebang, or `<event>.cmd` on Windows). hydra runs it at that
point with `HYDRA_*` env vars. A non-zero exit from a `pre-*` hook aborts that
step; `post-*` hook failures are reported but don't stop the run.

Events: pre-batch, post-batch, pre-task, post-task, pre-merge, post-merge.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

EVENTS = ("pre-batch", "post-batch", "pre-task", "post-task", "pre-merge", "post-merge")


def _find(root: Path, event: str) -> Path | None:
    d = root / ".hydra" / "hooks"
    for name in (event, f"{event}.py", f"{event}.sh", f"{event}.cmd", f"{event}.bat"):
        p = d / name
        if p.is_file():
            return p
    return None


def run_hook(root: str | Path, event: str, env: dict[str, str]) -> tuple[bool, str]:
    """(ok, output). ok is True when there is no hook or it exits 0."""
    root = Path(root)
    hook = _find(root, event)
    if hook is None:
        return True, ""
    if hook.suffix == ".py":
        argv = [sys.executable, str(hook)]
    elif hook.suffix in (".cmd", ".bat"):
        argv = [str(hook)]
    else:
        argv = ["sh", str(hook)] if sys.platform != "win32" else [str(hook)]
    full_env = {**os.environ, **{f"HYDRA_{k.upper()}": str(v) for k, v in env.items()},
                "HYDRA_EVENT": event}
    try:
        r = subprocess.run(argv, cwd=root, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=full_env, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"{event} hook failed to run: {e}"
    out = (r.stdout or "") + (r.stderr or "")
    return r.returncode == 0, out.strip()
