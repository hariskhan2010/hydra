"""hydra CLI.

`doctor` and `plan` do real work. The rest print the roadmap phase that will
implement them and exit non-zero, so nothing looks done that isn't (principle B5).
"""
from __future__ import annotations

import argparse
import sys

from . import __version__
from . import governor
from .errors import HydraError

# Roadmap text and agent output carry em-dashes / arrows. A cp1252 console or a
# non-UTF-8 pipe would mangle or crash them, so force UTF-8 and degrade instead.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# subcommand -> (roadmap phase, one-line description)
_PLANNED = {
    "run": (3, "execute all tasks: parallel dispatch, gate, merge"),
    "status": (3, "live run state"),
    "resume": (3, "continue a run from its last completed gate"),
    "reflect": (7, "distil recurring corrections into role lessons"),
    "serve": (6, "MCP server — let an agent drive hydra"),
}


def _cmd_doctor(args: argparse.Namespace) -> int:
    b = governor.compute(configured_max=args.max_agents)
    print("hydra doctor")
    print(f"  version        {__version__}")
    print(f"  python         {sys.version.split()[0]}")
    print(f"  platform       {sys.platform}")
    print(f"  cpu cores      {b.cores}")
    print("  free memory    "
          + (f"{b.free_gb:.1f} GiB" if b.free_gb is not None else "unknown"))
    print(f"  per-agent est. {b.per_agent_gb:g} GiB")
    print(f"  MAX AGENTS     {b.max_agents}")
    print(f"    reason       {b.reason}")
    return 0


def _cmd_plan(args: argparse.Namespace) -> int:
    from .planning import render_plan
    try:
        print(render_plan(args.tasks, max_agents=args.max_agents))
    except HydraError as e:
        print(f"hydra plan: {e}", file=sys.stderr)
        return 1
    return 0


def _cmd_dispatch(args: argparse.Namespace) -> int:
    from . import gitutil
    from .config import load_config
    from .dispatch import dispatch_one
    from .tasks import load_tasks

    try:
        tasks = {t.id: t for t in load_tasks(args.tasks)}
        if args.task_id not in tasks:
            raise HydraError(f"no task {args.task_id!r} in {args.tasks} "
                             f"(have: {', '.join(tasks)})")
        task = tasks[args.task_id]
        cfg = load_config(args.tasks)
        driver = cfg.driver()
        base = args.base or cfg.base_branch
        timeout = args.timeout or cfg.timeout

        print(f"hydra dispatch {task.id}  —  agent: {driver.name}")
        print(f"  command: {driver.display_command()}  (prompt on stdin)")
        if args.print_command:
            return 0
        if not driver.available():
            raise HydraError(f"agent {driver.name!r} is not on PATH")

        root = gitutil.repo_root(args.repo)
        print(f"  repo: {root}   base: {base}   worktree: .hydra/wt/{task.id}")
        print("  running…")
        res = dispatch_one(root, task, driver, base=base, timeout=timeout,
                           keep_worktree=args.keep)
    except HydraError as e:
        print(f"hydra dispatch: {e}", file=sys.stderr)
        return 1

    print(f"\n  agent: {'ok' if res.driver.ok else 'FAILED'} "
          f"in {res.driver.duration_s:.0f}s   files changed: {res.files_changed}")
    if res.error:
        print(f"  ! {res.error}", file=sys.stderr)
    if res.diff:
        print("\n----- diff -----")
        print(res.diff)
    if args.keep and res.worktree_path:
        print(f"\n  worktree kept: {res.worktree_path}  (branch {res.branch})")
        print(f"  remove with: git -C {res.worktree_path.parent.parent.parent} "
              f"worktree remove --force {res.worktree_path}")
    return 0 if res.ok else 1


def _cmd_planned(name: str):
    def run(_args: argparse.Namespace) -> int:
        phase, desc = _PLANNED[name]
        print(f"hydra {name}: not implemented yet — Phase {phase} ({desc}).",
              file=sys.stderr)
        print("see ROADMAP.md", file=sys.stderr)
        return 2
    return run


def build_parser() -> argparse.ArgumentParser:
    # --max-agents goes on each subcommand (put it after the command name)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--max-agents", type=int, default=None,
                        help="lower the concurrency ceiling (cannot raise it)")

    p = argparse.ArgumentParser(
        prog="hydra",
        description="A hardware-adaptive, agent-agnostic multi-agent orchestrator "
                    "for coding-agent CLIs. Pre-alpha.",
    )
    p.add_argument("-V", "--version", action="version",
                   version=f"hydra {__version__}")

    sub = p.add_subparsers(dest="command", metavar="<command>")

    d = sub.add_parser("doctor", parents=[common],
                       help="report hardware + the computed agent ceiling")
    d.set_defaults(func=_cmd_doctor)

    pl = sub.add_parser("plan", parents=[common],
                        help="dry-run: parallel-vs-sequential split + cost projection")
    pl.add_argument("tasks", nargs="?", default="tasks.toml",
                    help="task file (default: tasks.toml)")
    pl.set_defaults(func=_cmd_plan)

    ds = sub.add_parser("dispatch", parents=[common],
                        help="run ONE task end to end (worktree -> agent -> diff)")
    ds.add_argument("task_id")
    ds.add_argument("tasks", nargs="?", default="tasks.toml",
                    help="task file (default: tasks.toml)")
    ds.add_argument("--repo", default=".", help="target repo (default: cwd)")
    ds.add_argument("--base", default=None, help="branch/ref to cut the worktree from")
    ds.add_argument("--timeout", type=int, default=None, help="agent timeout in seconds")
    ds.add_argument("--keep", action="store_true", help="keep the worktree after")
    ds.add_argument("--print-command", action="store_true",
                    help="show the agent command and exit — spend nothing")
    ds.set_defaults(func=_cmd_dispatch)

    for name, (phase, desc) in _PLANNED.items():
        sp = sub.add_parser(name, parents=[common], help=f"[Phase {phase}] {desc}")
        sp.set_defaults(func=_cmd_planned(name))

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
