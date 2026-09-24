# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Goal batching. One attack instance per worker, log labels via contextvars."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from typing import Any, Callable, List, Sequence

from hackagent.attacks.types import AttackResult, flatten_run_result
from hackagent.core.contracts import Goal
from hackagent.core.logging import get_logger

logger = get_logger(__name__)

_batch_label: ContextVar[str] = ContextVar("hackagent_batch_label", default="")


class _BatchLabelFilter(logging.Filter):
    """Prefix log records emitted inside a goal-batch worker."""

    def filter(self, record: logging.LogRecord) -> bool:
        label = _batch_label.get()
        if label:
            message = record.getMessage()
            if not message.startswith(f"[{label}]"):
                record.msg = f"[{label}] {record.msg}"
                record.args = ()
        return True


def schedule(
    goals: Sequence[Goal],
    *,
    attack_factory: Callable[[], Any],
    batch_size: int | None,
    workers: int,
) -> List[AttackResult]:
    """Run *goals*, splitting into batches when ``batch_size`` is set.

    ``batch_size`` of ``None`` runs every goal in one ``run()`` call, which
    is the historical default when the caller did not ask for batching.
    Each worker builds its own attack instance.
    """
    texts = [goal.text for goal in goals]
    if not batch_size or batch_size <= 0:
        attack = attack_factory()
        return _as_results(attack.run(goals=texts))

    batches = [
        (start, texts[start : start + batch_size])
        for start in range(0, len(texts), batch_size)
    ]
    worker_count = max(1, int(workers))
    root = logging.getLogger()
    label_filter = _BatchLabelFilter()
    root.addFilter(label_filter)
    all_results: List[AttackResult] = []
    try:
        for batch_index, (start, batch_goals) in enumerate(batches):
            label = f"B{batch_index + 1}/{len(batches)}"
            logger.info("[%s] Starting (%d goals)", label, len(batch_goals))
            if worker_count <= 1:
                attack = attack_factory()
                _stamp_offset(attack, start)
                all_results.extend(_as_results(attack.run(goals=batch_goals)))
                continue
            all_results.extend(
                _run_parallel(
                    batch_goals,
                    start=start,
                    label=label,
                    workers=min(worker_count, len(batch_goals)),
                    attack_factory=attack_factory,
                )
            )
    finally:
        root.removeFilter(label_filter)
    return all_results


def _run_parallel(
    batch_goals: Sequence[str],
    *,
    start: int,
    label: str,
    workers: int,
    attack_factory: Callable[[], Any],
) -> List[AttackResult]:
    n_goals = len(batch_goals)

    def _one(item: tuple[int, str]) -> tuple[int, List[AttackResult]]:
        index, goal = item
        token = _batch_label.set(f"{label} G{index + 1}/{n_goals}")
        try:
            attack = attack_factory()
            _stamp_offset(attack, start + index)
            logger.info("Processing goal: %s", goal[:60])
            return index, _as_results(attack.run(goals=[goal]))
        finally:
            _batch_label.reset(token)

    ordered: dict[int, List[AttackResult]] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for index, rows in pool.map(_one, enumerate(batch_goals)):
            ordered[index] = rows
    results: List[AttackResult] = []
    for index in range(n_goals):
        results.extend(ordered.get(index, []))
    return results


def _stamp_offset(attack: Any, offset: int) -> None:
    config = getattr(attack, "config", None)
    if isinstance(config, dict):
        config["_goal_index_offset"] = offset
        config["_suppress_run_status_updates"] = True


def _as_results(value: Any) -> List[AttackResult]:
    rows = flatten_run_result(value)
    results: List[AttackResult] = []
    for row in rows:
        if isinstance(row, AttackResult):
            results.append(row)
        else:
            results.append(AttackResult.from_row(row))
    return results


__all__ = ["schedule"]
