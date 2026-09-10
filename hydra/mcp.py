"""`hydra serve` — a minimal MCP server over stdio (A10).

Newline-delimited JSON-RPC 2.0 on stdin/stdout. No SDK — stdlib only (C2).
Exposes hydra's commands as tools an agent can call.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import __version__, gitutil
from .config import load_config
from .errors import HydraError

PROTOCOL_VERSION = "2025-06-18"

_TOOLS = [
    {"name": "hydra_doctor", "description": "Report hardware and the computed agent ceiling.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "hydra_plan",
     "description": "Dry-run: parallel/sequential batches + token projection for a task file.",
     "inputSchema": {"type": "object", "properties": {
         "tasks": {"type": "string", "description": "path to the task TOML"},
         "max_agents": {"type": "integer"}}, "required": ["tasks"]}},
    {"name": "hydra_run",
     "description": "Execute every task in the file (parallel, governor-capped). Returns the run's state table.",
     "inputSchema": {"type": "object", "properties": {
         "tasks": {"type": "string"}, "max_agents": {"type": "integer"},
         "base": {"type": "string"}}, "required": ["tasks"]}},
    {"name": "hydra_status",
     "description": "Show a run's state table (latest run if run_id omitted).",
     "inputSchema": {"type": "object", "properties": {"run_id": {"type": "string"}}}},
    {"name": "hydra_context",
     "description": "Show or FTS-search a run's shared memory.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string"}, "run_id": {"type": "string"}}}},
    {"name": "hydra_merge",
     "description": "Review-gate each task's diff then merge in dependency order into hydra/run-<id>.",
     "inputSchema": {"type": "object", "properties": {
         "run_id": {"type": "string"}, "review": {"enum": ["rule", "agent"]}}}},
]


def _text(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}], "isError": False}


def _err(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}], "isError": True}


def _call(name: str, args: dict, repo: str) -> dict:
    try:
        if name == "hydra_doctor":
            from .governor import compute
            b = compute()
            return _text(f"cores {b.cores}, free {b.free_gb} GiB -> MAX AGENTS {b.max_agents}\n{b.reason}")

        if name == "hydra_plan":
            from .planning import render_plan
            return _text(render_plan(args["tasks"], max_agents=args.get("max_agents")))

        if name == "hydra_run":
            from .runner import run as run_tasks
            root = gitutil.repo_root(repo)
            cfg = load_config(args["tasks"])
            drv = cfg.driver()
            log: list[str] = []
            out = run_tasks(root, args["tasks"], cfg, drv,
                            max_agents=args.get("max_agents"), base=args.get("base"),
                            on_event=log.append)
            return _text("\n".join(log) + "\n\n" + out.state.render_table())

        if name == "hydra_status":
            from .runstate import RunState
            root = gitutil.repo_root(repo)
            return _text(RunState.load(root, args.get("run_id")).render_table())

        if name == "hydra_context":
            from .runstate import RunState
            from .sharedmem import SharedContext
            root = gitutil.repo_root(repo)
            st = RunState.load(root, args.get("run_id"))
            sc = SharedContext(Path(root) / ".hydra" / "runs" / st.run_id)
            q = args.get("query")
            body = "\n\n".join(sc.search(q)) if q else sc.current(100_000)
            sc.close()
            return _text(body or "(shared memory empty)")

        if name == "hydra_merge":
            from .merge import merge_run
            from .runstate import RunState
            from .tasks import load_tasks
            root = gitutil.repo_root(repo)
            st = RunState.load(root, args.get("run_id"))
            cfg = load_config(st.task_file)
            by_id = {t.id: t for t in load_tasks(st.task_file)}
            mode = args.get("review") or cfg.review_mode
            drv = cfg.driver() if mode == "agent" else None
            log: list[str] = []
            m = merge_run(root, st, by_id, review_mode=mode, driver=drv, on_event=log.append)
            tail = (f"\nmerged {m.merged} -> {m.integration_branch}" if m.ok
                    else f"\nblocked: {m.blocked} conflict: {m.conflicted}")
            return _text("\n".join(log) + tail)

        return _err(f"unknown tool {name!r}")
    except HydraError as e:
        return _err(str(e))
    except Exception as e:  # never crash the server on a tool error
        return _err(f"{type(e).__name__}: {e}")


def serve(repo: str = ".") -> int:
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        mid = msg.get("id")
        method = msg.get("method")

        if method == "initialize":
            result = {"protocolVersion": PROTOCOL_VERSION,
                      "capabilities": {"tools": {}},
                      "serverInfo": {"name": "hydra", "version": __version__}}
        elif method == "tools/list":
            result = {"tools": _TOOLS}
        elif method == "tools/call":
            p = msg.get("params", {})
            result = _call(p.get("name", ""), p.get("arguments", {}) or {}, repo)
        elif method in ("notifications/initialized", "notifications/cancelled"):
            continue  # notifications: no response
        elif method == "ping":
            result = {}
        else:
            if mid is not None:
                _send({"jsonrpc": "2.0", "id": mid,
                       "error": {"code": -32601, "message": f"method not found: {method}"}})
            continue

        if mid is not None:
            _send({"jsonrpc": "2.0", "id": mid, "result": result})
    return 0


def _send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()
