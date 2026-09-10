"""The file-set independence proof — hydra's answer to Ruflo's consensus layer.

Two tasks may run in parallel only when BOTH hold:
  1. neither depends (transitively) on the other, and
  2. their declared file touch-sets are provably disjoint.

Anything we cannot *prove* disjoint is treated as a conflict and serialised
(principle C4 / B1: refuse to parallelise when independence is unproven).

`plan_waves` returns an ordered list of batches. Every task in a batch is
mutually independent, so the batch can be dispatched concurrently (subject to
the hardware governor). Batches run in sequence.
"""
from __future__ import annotations

from dataclasses import dataclass

from .errors import HydraError
from .tasks import Task


# ---- file-spec overlap -------------------------------------------------------

def _is_glob(s: str) -> bool:
    return any(c in s for c in "*?[")


def specs_overlap(a: str, b: str) -> bool:
    """True if file-specs `a` and `b` could match a common path.

    Conservative: when the relationship can't be decided cleanly, return True.
    Handles exact paths and `dir/**` prefixes precisely; treats other globs
    (`*.py`, `src/*/x`) conservatively.
    """
    if a == b:
        return True

    a_pref = a[:-3] if a.endswith("/**") else None
    b_pref = b[:-3] if b.endswith("/**") else None

    if a_pref is not None and b_pref is not None:
        return a_pref == b_pref or a_pref.startswith(b_pref + "/") or b_pref.startswith(a_pref + "/")
    if a_pref is not None and not _is_glob(b):
        return b == a_pref or b.startswith(a_pref + "/")
    if b_pref is not None and not _is_glob(a):
        return a == b_pref or a.startswith(b_pref + "/")

    if not _is_glob(a) and not _is_glob(b):
        return a == b

    # at least one is a non-`/**` glob — can't prove disjoint cheaply
    return True


def files_conflict(t1: Task, t2: Task) -> list[tuple[str, str]]:
    # No declared touch-set on either side => independence is unprovable => treat
    # as a conflict and serialise (principle B1).
    if not t1.files or not t2.files:
        return [("<undeclared>", "<undeclared>")]
    hits = []
    for x in t1.files:
        for y in t2.files:
            if specs_overlap(x, y):
                hits.append((x, y))
    return hits


# ---- dependency layering ---------------------------------------------------

def _dependency_layers(tasks: list[Task]) -> list[list[str]]:
    by_id = {t.id: t for t in tasks}
    indeg = {t.id: len(t.depends_on) for t in tasks}
    dependents: dict[str, list[str]] = {t.id: [] for t in tasks}
    for t in tasks:
        for d in t.depends_on:
            dependents[d].append(t.id)

    layers: list[list[str]] = []
    ready = sorted(tid for tid, n in indeg.items() if n == 0)
    placed = 0
    while ready:
        layers.append(ready)
        placed += len(ready)
        nxt: list[str] = []
        for tid in ready:
            for child in dependents[tid]:
                indeg[child] -= 1
                if indeg[child] == 0:
                    nxt.append(child)
        ready = sorted(nxt)
    if placed != len(tasks):
        stuck = sorted(tid for tid, n in indeg.items() if n > 0)
        raise HydraError(f"dependency cycle among tasks: {stuck}")
    return layers


# ---- the plan -------------------------------------------------------------

@dataclass
class Batch:
    index: int
    task_ids: list[str]
    # why each pair that COULD have shared a dependency-layer was still split
    split_notes: list[str]


@dataclass
class WavePlan:
    batches: list[Batch]
    parallelizable: bool  # any batch has > 1 task

    @property
    def max_batch_size(self) -> int:
        return max((len(b.task_ids) for b in self.batches), default=0)


def _split_by_files(layer_ids: list[str], by_id: dict[str, Task]) -> tuple[list[list[str]], list[str]]:
    """Greedily partition one dependency-layer into file-independent groups."""
    groups: list[list[str]] = []
    notes: list[str] = []
    for tid in layer_ids:
        t = by_id[tid]
        for g in groups:
            clash = None
            for other in g:
                hits = files_conflict(t, by_id[other])
                if hits:
                    clash = (other, hits[0])
                    break
            if clash is None:
                g.append(tid)
                break
        else:
            groups.append([tid])
            continue
        # landed in a group; if it clashed with a *different* group, note it
        for g2 in groups:
            if tid in g2:
                continue
            for other in g2:
                hits = files_conflict(t, by_id[other])
                if hits:
                    x, y = hits[0]
                    notes.append(f"{tid} and {other} kept apart — {x} ~ {y}")
                    break
    return groups, notes


def plan_waves(tasks: list[Task]) -> WavePlan:
    if not tasks:
        raise HydraError("no tasks to plan")
    by_id = {t.id: t for t in tasks}
    layers = _dependency_layers(tasks)

    batches: list[Batch] = []
    for layer in layers:
        groups, notes = _split_by_files(layer, by_id)
        for g in groups:
            batches.append(Batch(index=len(batches), task_ids=g,
                                 split_notes=notes if len(groups) > 1 else []))
    return WavePlan(batches=batches,
                    parallelizable=any(len(b.task_ids) > 1 for b in batches))
