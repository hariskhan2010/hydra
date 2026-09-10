"""`hydra run --remote <host>` (B8) — laptop is the control plane, a bigger box
does the parallel work.

    1. rsync the repo (minus .git internals we don't need) to host:<remote_root>
    2. ssh in and run `hydra run <tasks> <args>` there, streaming output back
    3. rsync `.hydra/` back, and `git fetch` the run's branches from the remote

Needs `rsync` + `ssh` on this machine and `hydra` + `git` on the host. Nothing
here can be unit-tested against a real host, so `plan_remote()` returns the exact
commands and `--dry-run` prints them without connecting.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from . import gitutil
from .errors import HydraError


@dataclass
class RemotePlan:
    host: str
    remote_root: str
    push: list[str]
    execute: list[str]
    pull: list[str]
    fetch: list[str]

    def all(self) -> list[list[str]]:
        return [self.push, self.execute, self.pull, self.fetch]


def plan_remote(root: str | Path, host: str, tasks: str, run_args: list[str], *,
                remote_base: str = "~/.hydra-remote") -> RemotePlan:
    root = gitutil.repo_root(root)
    name = root.name
    remote_root = f"{remote_base}/{name}"
    ssh_target = host if "@" in host or ":" not in host else host

    push = ["rsync", "-a", "--delete",
            "--exclude", ".hydra/wt", "--exclude", ".hydra/runs",
            f"{root}/", f"{ssh_target}:{remote_root}/"]
    execute = ["ssh", ssh_target,
               f"cd {remote_root} && hydra run {tasks} " + " ".join(run_args)]
    pull = ["rsync", "-a", f"{ssh_target}:{remote_root}/.hydra/", f"{root}/.hydra/"]
    fetch = ["git", "-C", str(root), "fetch",
             f"ssh://{ssh_target}/{remote_root}",
             "refs/heads/hydra/*:refs/heads/hydra/*"]
    return RemotePlan(host=host, remote_root=remote_root,
                      push=push, execute=execute, pull=pull, fetch=fetch)


def run_remote(root: str | Path, host: str, tasks: str, run_args: list[str], *,
               dry_run: bool = False, on_event=None) -> int:
    emit = on_event or (lambda _m: None)
    for tool in ("rsync", "ssh"):
        if not dry_run and shutil.which(tool) is None:
            raise HydraError(f"{tool} not on PATH — required for --remote")

    plan = plan_remote(root, host, tasks, run_args)
    if dry_run:
        for step, cmd in zip(("push", "execute", "pull", "fetch"), plan.all()):
            emit(f"# {step}\n{' '.join(cmd)}")
        return 0

    for step, cmd in zip(("push", "execute", "pull", "fetch"), plan.all()):
        emit(f"[{step}] {' '.join(cmd)}")
        r = subprocess.run(cmd, text=True)
        if r.returncode != 0 and step in ("push", "execute"):
            raise HydraError(f"remote {step} failed (exit {r.returncode})")
    emit(f"done. remote run's branches fetched into {gitutil.repo_root(root)} as hydra/*")
    return 0
