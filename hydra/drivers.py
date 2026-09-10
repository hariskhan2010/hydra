"""Agent drivers — hydra is agent-agnostic (principle B2).

A driver turns a task prompt + a working directory into an agent process that
edits files in that directory. Built-in: `claude`, `qwen`, and `generic`
(a command template from `hydra.toml`). Prompts go on **stdin** so a long
prompt can't hit an argv length limit.
"""
from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass, field


@dataclass
class DriverResult:
    ok: bool
    stdout: str
    stderr: str
    duration_s: float
    error: str | None = None


class Driver:
    name = "base"
    #: extra CLI args appended after the built-ins (from hydra.toml [agent].args)
    extra_args: list[str] = []

    def exe(self) -> str | None:
        return None

    def available(self) -> bool:
        return self.exe() is not None

    def argv(self) -> list[str]:
        raise NotImplementedError

    def display_command(self) -> str:
        return " ".join(self.argv() or [f"<{self.name} not found on PATH>"])

    def run(self, prompt: str, cwd: str, timeout: int) -> DriverResult:
        argv = self.argv()
        if not argv:
            return DriverResult(False, "", "", 0.0, f"{self.name} not found on PATH")
        t0 = time.time()
        try:
            r = subprocess.run(argv, input=prompt, cwd=cwd, capture_output=True,
                               text=True, encoding="utf-8", errors="replace",
                               timeout=timeout)
        except subprocess.TimeoutExpired:
            return DriverResult(False, "", "", time.time() - t0,
                                f"{self.name} timed out after {timeout}s")
        except OSError as e:
            return DriverResult(False, "", "", time.time() - t0, f"{self.name}: {e}")
        dt = time.time() - t0
        ok = r.returncode == 0
        return DriverResult(ok, r.stdout, r.stderr, dt,
                            None if ok else f"{self.name} exited {r.returncode}")


@dataclass
class ClaudeDriver(Driver):
    name: str = "claude"
    extra_args: list[str] = field(default_factory=lambda: ["--permission-mode", "acceptEdits"])

    def exe(self) -> str | None:
        return shutil.which("claude")

    def argv(self) -> list[str]:
        exe = self.exe()
        if not exe:
            return []
        return [exe, "-p", "--output-format", "text", *self.extra_args]


@dataclass
class QwenDriver(Driver):
    name: str = "qwen"
    extra_args: list[str] = field(default_factory=lambda: ["--approval-mode", "yolo"])

    def exe(self) -> str | None:
        return shutil.which("qwen")

    def argv(self) -> list[str]:
        exe = self.exe()
        if not exe:
            return []
        return [exe, "-p", *self.extra_args]


@dataclass
class GenericDriver(Driver):
    name: str = "generic"
    template: list[str] = field(default_factory=list)  # e.g. ["mycli", "--prompt-stdin"]
    extra_args: list[str] = field(default_factory=list)

    def exe(self) -> str | None:
        if not self.template:
            return None
        return shutil.which(self.template[0]) or (self.template[0]
                                                  if "/" in self.template[0] or "\\" in self.template[0]
                                                  else None)

    def argv(self) -> list[str]:
        if not self.template:
            return []
        head = shutil.which(self.template[0]) or self.template[0]
        return [head, *self.template[1:], *self.extra_args]


_BUILTIN = {"claude": ClaudeDriver, "qwen": QwenDriver, "generic": GenericDriver}


def build_driver(kind: str, *, template: list[str] | None = None,
                 extra_args: list[str] | None = None) -> Driver:
    cls = _BUILTIN.get(kind)
    if cls is None:
        from .errors import HydraError
        raise HydraError(f"unknown agent kind {kind!r} (expected: {', '.join(_BUILTIN)})")
    if cls is GenericDriver:
        d = GenericDriver(template=list(template or []))
    else:
        d = cls()
    if extra_args is not None:
        d.extra_args = list(extra_args)
    return d


def autodetect() -> Driver | None:
    for cls in (ClaudeDriver, QwenDriver):
        d = cls()
        if d.available():
            return d
    return None
