"""A deliberately rough token / cost projection for `hydra plan`.

This is a planning aid, not a promise. It exists so you see the shape of the
spend before dispatching a token (principle B6), and so the hard cost ceiling
(Phase 6, B7) has something to compare against.

Model: an agent turn on a task costs roughly
    prompt_tokens  ~ shared_context + task_prompt + files_touched * PER_FILE_IN
    output_tokens  ~ files_touched * PER_FILE_OUT
times an assumed number of ROUNDS of edit/observe.
"""
from __future__ import annotations

from dataclasses import dataclass

from .tasks import Task

SHARED_CONTEXT_TOKENS = 1500
PER_FILE_IN = 700          # reading/understanding one target file
PER_FILE_OUT = 400         # writing one target file
ROUNDS = 3                 # edit → run → fix
CHARS_PER_TOKEN = 4


@dataclass
class TaskEstimate:
    task_id: str
    input_tokens: int
    output_tokens: int

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


def estimate_task(t: Task) -> TaskEstimate:
    nfiles = max(1, len(t.files))
    prompt_tok = len(t.prompt) // CHARS_PER_TOKEN
    per_round_in = SHARED_CONTEXT_TOKENS + prompt_tok + nfiles * PER_FILE_IN
    per_round_out = nfiles * PER_FILE_OUT
    return TaskEstimate(
        task_id=t.id,
        input_tokens=per_round_in * ROUNDS,
        output_tokens=per_round_out * ROUNDS,
    )


def estimate_run(tasks: list[Task]) -> list[TaskEstimate]:
    return [estimate_task(t) for t in tasks]


def dollars(estimates: list[TaskEstimate],
            price_in_per_mtok: float, price_out_per_mtok: float) -> float:
    tin = sum(e.input_tokens for e in estimates)
    tout = sum(e.output_tokens for e in estimates)
    return tin / 1e6 * price_in_per_mtok + tout / 1e6 * price_out_per_mtok
