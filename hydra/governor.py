"""Hardware governor — decides how many agents may run at once.

Principle C3: concurrency is a function of the machine, not ambition.
`--max-agents` can only lower the ceiling this computes, never raise it.

stdlib only: `os.cpu_count()` plus a best-effort free-memory read per platform.
"""
from __future__ import annotations

import ctypes
import os
import sys
from dataclasses import dataclass

# How much resident memory one agent subprocess is assumed to need. Deliberately
# conservative — an editor CLI plus its language tooling is not small.
PER_AGENT_GB = 2.0


def _free_memory_gb() -> float | None:
    """Best-effort available (not just free) memory in GiB, or None if unknown."""
    try:
        if sys.platform == "win32":
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return stat.ullAvailPhys / (1024 ** 3)
            return None

        # Linux / WSL
        meminfo = {}
        with open("/proc/meminfo", encoding="ascii") as fh:
            for line in fh:
                key, _, rest = line.partition(":")
                meminfo[key.strip()] = rest.strip()
        for key in ("MemAvailable", "MemFree"):
            if key in meminfo:
                kb = int(meminfo[key].split()[0])
                return kb / (1024 ** 2)
        return None
    except Exception:
        return None


@dataclass
class Budget:
    cores: int
    free_gb: float | None
    per_agent_gb: float
    configured_max: int | None
    max_agents: int
    reason: str


def compute(configured_max: int | None = None) -> Budget:
    cores = os.cpu_count() or 1
    free_gb = _free_memory_gb()

    by_cpu = max(1, cores - 1)  # leave one core for the orchestrator + OS
    if free_gb is None:
        by_mem = by_cpu
        mem_note = "memory unknown, ignored"
    else:
        by_mem = max(1, int(free_gb // PER_AGENT_GB))
        mem_note = f"{free_gb:.1f} GiB free / {PER_AGENT_GB:g} per agent -> {by_mem}"

    ceiling = min(by_cpu, by_mem)
    limit = ceiling
    reason = f"min(cpu {by_cpu} [{cores} cores - 1], mem {by_mem} [{mem_note}])"
    if configured_max is not None:
        limit = min(ceiling, max(1, configured_max))
        reason += f", lowered to configured max {configured_max}" if configured_max < ceiling \
            else f", configured max {configured_max} >= ceiling so ignored"

    return Budget(
        cores=cores,
        free_gb=free_gb,
        per_agent_gb=PER_AGENT_GB,
        configured_max=configured_max,
        max_agents=limit,
        reason=reason,
    )
