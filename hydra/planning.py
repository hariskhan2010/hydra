"""`hydra plan` — the dry run.

Loads tasks, proves which can run in parallel, applies the hardware governor,
projects token cost, and prints the batch layout. Dispatches nothing.
"""
from __future__ import annotations

from pathlib import Path

from . import estimate, governor
from .config import load_config
from .independence import WavePlan, plan_waves
from .tasks import Task, load_tasks


def render_plan(task_file: str | Path, *, max_agents: int | None = None) -> str:
    task_file = Path(task_file)
    tasks = load_tasks(task_file)
    by_id = {t.id: t for t in tasks}
    wp: WavePlan = plan_waves(tasks)
    budget = governor.compute(configured_max=max_agents)
    ests = {e.task_id: e for e in estimate.estimate_run(tasks)}

    lines: list[str] = []
    lines.append(f"hydra plan — {task_file}")
    lines.append(f"  {len(tasks)} task(s), {len(wp.batches)} batch(es), "
                 f"governor allows {budget.max_agents} concurrent")
    lines.append(f"  governor: {budget.reason}")
    lines.append("")

    wall = 0          # tokens on the critical path given the governor
    serial_total = 0  # tokens if every task ran one after another
    used_parallelism = False
    for b in wp.batches:
        n = len(b.task_ids)
        conc = max(1, min(n, budget.max_agents))
        if n > 1 and conc > 1:
            used_parallelism = True
        tag = f"parallel x{n}" if n > 1 else "single"
        if n > 1 and conc < n:
            tag += f" (governor runs {conc} at a time)"
        lines.append(f"  batch {b.index}  [{tag}]")
        totals = []
        for tid in b.task_ids:
            t: Task = by_id[tid]
            e = ests[tid]
            serial_total += e.total
            totals.append(e.total)
            files = ", ".join(t.files) if t.files else "(no files declared — serialised)"
            lines.append(f"    - {tid}: {t.title}")
            lines.append(f"        files: {files}")
            lines.append(f"        est:   ~{e.input_tokens:,} in / ~{e.output_tokens:,} out")
        # critical path for this batch = makespan lower bound with `conc`
        # workers: no faster than the slowest single task, nor than an even
        # split of the batch's total work. conc==1 collapses this to the sum.
        if totals:
            wall += max(max(totals), -(-sum(totals) // conc))
        for note in b.split_notes:
            lines.append(f"    ! {note}")
        lines.append("")

    if not wp.parallelizable:
        verdict = "no parallelism available (dependencies / shared files)"
    elif not used_parallelism:
        verdict = f"parallelism available but governor caps to {budget.max_agents} — no speedup here"
    else:
        verdict = f"~{100 - round(wall / serial_total * 100)}% shorter than fully serial"

    lines.append("  token estimate (rough):")
    lines.append(f"    total work      ~{serial_total:,} tokens (sum of all tasks)")
    lines.append(f"    critical path   ~{wall:,} tokens — {verdict}")

    pricing = load_config(task_file).pricing
    if pricing:
        pin, pout = pricing
        usd = estimate.dollars(list(ests.values()), pin, pout)
        lines.append(f"    est. cost       ~${usd:,.2f} "
                     f"(hydra.toml pricing: ${pin}/${pout} per Mtok)")
    else:
        lines.append(f"    est. cost       set [pricing] in hydra.toml for a $ figure")

    lines.append("")
    lines.append("  nothing dispatched. `hydra run` executes this (Phase 3).")
    return "\n".join(lines)
