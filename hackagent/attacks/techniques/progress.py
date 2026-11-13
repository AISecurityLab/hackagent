# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Operational attack progress, scoped to each concurrent goal.

Only algorithm stages, numeric positions and counts leave a trace through
this channel. Prompts, replies, programs and free-form decision reasons do
not belong in live activity.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Optional

Callback = Callable[..., None]
_observer: ContextVar[Optional[Callback]] = ContextVar("attack_progress", default=None)
_NUMBERED = re.compile(
    r"(depth|round|turn|iteration|stream|branch|candidate|query|selection|warm-up goal|"
    r"attempt|prefix|program|synthesis round) "
    r"(\d+)(?:/(\d+))?"
)
_EPOCH = re.compile(r"round (\d+)\.(\d+)")
_CANDIDATE = re.compile(r"step (\d+)/(\d+), candidate (\d+)/(\d+)")
_TECHNIQUE = re.compile(r"technique (\d+)/(\d+): .+", re.DOTALL)
_PHASES = {
    "expand",
    "candidate",
    "on topic",
    "panel review",
    "write",
    "poison",
    "queries",
    "index",
    "tool-chain",
    "retrieval",
    "selection",
}
_COUNTS = {
    "branches",
    "candidates",
    "dropped",
    "kept",
    "backtracks",
    "documents",
    "chunks",
}
_DECISIONS = {"stopped", "pruned", "skipped", "refused", "backtracked", "kept"}


@contextmanager
def observe_progress(callback: Callback) -> Iterator[None]:
    """Observe algorithm progress in this task and tasks it starts."""
    token = _observer.set(callback)
    try:
        yield
    finally:
        _observer.reset(token)


def emit_progress(event: str, **payload: Any) -> None:
    """Send an operational event to the current goal's listener."""
    callback = _observer.get()
    if callback is not None:
        callback(event, **payload)


def phase_progress(
    label: str, path: tuple[int, ...], data: Mapping[str, Any], stage: str
) -> None:
    """Describe a known algorithm phase without forwarding arbitrary labels."""
    match = _NUMBERED.fullmatch(label)
    phase = (
        "round"
        if match and match[1] in {"depth", "synthesis round"}
        else match[1]
        if match
        else label
    )
    fields: dict[str, Any] = {
        "phase": phase if match or phase in _PHASES else "attack phase",
        "path": list(path),
        "stage": stage,
    }
    if match:
        fields["step"] = int(match[2])
        if match[3]:
            fields["total"] = int(match[3])
    # Some techniques include display text or a second numeric position in
    # their trace label. Retain only the numeric coordinates, never the text.
    if epoch := _EPOCH.fullmatch(label):
        fields.update(phase="round", step=int(epoch[1]), epoch=int(epoch[2]))
    elif candidate := _CANDIDATE.fullmatch(label):
        fields.update(
            phase="iteration",
            step=int(candidate[1]),
            total=int(candidate[2]),
            candidate=int(candidate[3]),
            candidates=int(candidate[4]),
        )
    elif technique := _TECHNIQUE.fullmatch(label):
        fields.update(
            phase="technique", step=int(technique[1]), total=int(technique[2])
        )
    fields.update(
        {
            key: value
            for key, value in data.items()
            if key in _COUNTS and type(value) is int and value >= 0
        }
    )
    emit_progress("attack_progress", **fields)


def decision_progress(outcome: str, data: Mapping[str, Any]) -> None:
    """Report a search decision by its label and counts, without its reason."""
    if outcome in _DECISIONS:
        emit_progress(
            "attack_progress",
            stage="decision",
            phase=outcome,
            **{
                key: value
                for key, value in data.items()
                if key in _COUNTS and type(value) is int and value >= 0
            },
        )
