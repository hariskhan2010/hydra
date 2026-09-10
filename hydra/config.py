"""`hydra.toml` — optional. Sensible defaults when it's absent.

    [agent]
    kind = "claude"                 # claude | qwen | generic
    args = ["--permission-mode", "acceptEdits"]
    template = ["mycli", "--stdin"] # generic only
    timeout = 900

    [run]
    base_branch = "HEAD"            # branch/ref worktrees are cut from

    [pricing]                       # for `hydra plan` $ estimates
    input_per_mtok = 3.0
    output_per_mtok = 15.0
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .drivers import Driver, autodetect, build_driver
from .errors import HydraError


@dataclass
class Config:
    agent_kind: str | None
    agent_args: list[str] | None
    agent_template: list[str]
    timeout: int
    base_branch: str
    pricing: tuple[float, float] | None
    source: Path | None
    budget_tokens: int | None = None
    review_mode: str = "rule"   # rule | agent

    def driver(self) -> Driver:
        if self.agent_kind is None:
            d = autodetect()
            if d is None:
                raise HydraError(
                    "no agent CLI found (looked for `claude`, `qwen`). "
                    "Install one, or set [agent].kind + [agent].template in hydra.toml")
            return d
        return build_driver(self.agent_kind, template=self.agent_template,
                            extra_args=self.agent_args)


def _defaults(source: Path | None) -> Config:
    return Config(agent_kind=None, agent_args=None, agent_template=[],
                  timeout=900, base_branch="HEAD", pricing=None, source=source)


def load_config(start: str | Path) -> Config:
    start = Path(start)
    root = start if start.is_dir() else start.parent
    cfg_path = root / "hydra.toml"
    if not cfg_path.exists():
        return _defaults(None)
    try:
        data = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise HydraError(f"{cfg_path}: invalid TOML — {e}") from e

    c = _defaults(cfg_path)
    agent = data.get("agent", {}) or {}
    if "kind" in agent:
        c.agent_kind = str(agent["kind"])
    if "args" in agent:
        c.agent_args = [str(x) for x in agent["args"]]
    if "template" in agent:
        c.agent_template = [str(x) for x in agent["template"]]
    if "timeout" in agent:
        c.timeout = int(agent["timeout"])

    run = data.get("run", {}) or {}
    if "base_branch" in run:
        c.base_branch = str(run["base_branch"])

    pricing = data.get("pricing", {}) or {}
    try:
        if "input_per_mtok" in pricing and "output_per_mtok" in pricing:
            c.pricing = (float(pricing["input_per_mtok"]), float(pricing["output_per_mtok"]))
    except (TypeError, ValueError):
        c.pricing = None

    budget = data.get("budget", {}) or {}
    if "tokens" in budget:
        try:
            c.budget_tokens = int(budget["tokens"])
        except (TypeError, ValueError):
            c.budget_tokens = None

    rev = data.get("review", {}) or {}
    if str(rev.get("mode", "")).lower() in ("rule", "agent"):
        c.review_mode = str(rev["mode"]).lower()
    return c
