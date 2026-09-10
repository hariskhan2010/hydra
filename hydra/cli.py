"""hydra CLI — Phase 0 skeleton.

Every subcommand is wired to argparse. Only `doctor` and `--version` do real
work in Phase 0; the rest print the phase that will implement them (see
ROADMAP.md) and exit non-zero so nothing looks done that isn't — principle B5.
"""
from __future__ import annotations

import argparse
import sys

from . import __version__
from . import governor

# Roadmap text and agent output carry em-dashes / arrows. A cp1252 console or a
# non-UTF-8 pipe would mangle or crash them, so force UTF-8 and degrade instead.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# subcommand -> (roadmap phase, one-line description)
_PLANNED = {
    "plan": (1, "dry-run: parallel-vs-sequential split + cost projection"),
    "run": (3, "execute: worktree per task, dispatch, gate, merge"),
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


def _cmd_planned(name: str):
    def run(_args: argparse.Namespace) -> int:
        phase, desc = _PLANNED[name]
        print(f"hydra {name}: not implemented yet — Phase {phase} ({desc}).",
              file=sys.stderr)
        print("see ROADMAP.md", file=sys.stderr)
        return 2
    return run


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hydra",
        description="A hardware-adaptive, agent-agnostic multi-agent orchestrator "
                    "for coding-agent CLIs. Pre-alpha (Phase 0).",
    )
    p.add_argument("-V", "--version", action="version",
                   version=f"hydra {__version__}")
    p.add_argument("--max-agents", type=int, default=None,
                   help="lower the concurrency ceiling (cannot raise it)")

    sub = p.add_subparsers(dest="command", metavar="<command>")

    d = sub.add_parser("doctor", help="report hardware + the computed agent ceiling")
    d.set_defaults(func=_cmd_doctor)

    for name, (phase, desc) in _PLANNED.items():
        sp = sub.add_parser(name, help=f"[Phase {phase}] {desc}")
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
