# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Resolve attack goal sources into typed ``Goal`` values."""

from __future__ import annotations

from typing import Any, Dict, Optional

from hackagent.core.contracts import Goal
from hackagent.core.logging import get_logger
from hackagent.datasets.intents import load_goals_from_intents_config
from hackagent.datasets.registry import load_goals_and_extra_fields_from_config

logger = get_logger(__name__)

_SOURCE_PRECEDENCE = ("goals", "intents", "dataset")


def resolve_goals(
    *,
    goals: Optional[Any] = None,
    dataset: Optional[Any] = None,
    intents: Optional[Any] = None,
) -> list[Goal]:
    """Resolve explicit goals, intents, or a dataset into typed ``Goal`` values.

    Precedence is ``goals`` > ``intents`` > ``dataset``. When more than one
    source is provided, a single warning names the ignored sources and the
    winner is used.
    """
    sources: Dict[str, Any] = {
        "goals": goals,
        "intents": intents,
        "dataset": dataset,
    }
    provided = [name for name in _SOURCE_PRECEDENCE if sources[name] is not None]
    if not provided:
        raise ValueError(
            "Must provide one of 'goals' (list), 'dataset' (config), or 'intents' (config)"
        )

    source = provided[0]
    ignored = provided[1:]
    if ignored:
        logger.warning(
            "Multiple goal sources provided; using '%s' and ignoring: %s",
            source,
            ", ".join(ignored),
        )

    if source == "goals":
        resolved = _goals_from_explicit(goals)
    elif source == "intents":
        resolved = _goals_from_intents(intents)
    else:
        resolved = _goals_from_dataset(dataset)

    if not resolved:
        raise ValueError("Resolved goals list is empty")

    return resolved


def _goals_from_explicit(goals: Any) -> list[Goal]:
    if isinstance(goals, str) or not isinstance(goals, list):
        raise ValueError("'goals' must be a list of strings")
    if not all(isinstance(item, str) for item in goals):
        raise ValueError("'goals' must be a list of strings")
    return [
        Goal(text=text, index=index, labels={}, extra={})
        for index, text in enumerate(goals)
    ]


def _goals_from_intents(intents: Any) -> list[Goal]:
    try:
        texts, labels_by_index = load_goals_from_intents_config(intents)
    except Exception as exc:
        raise ValueError(f"Failed to load goals from intents: {exc}") from exc

    return [
        Goal(
            text=text,
            index=index,
            labels=dict(labels_by_index.get(index, {})),
            extra={},
        )
        for index, text in enumerate(texts)
    ]


def _goals_from_dataset(dataset: Any) -> list[Goal]:
    config: Any = {"preset": dataset} if isinstance(dataset, str) else dataset
    try:
        texts, extra_fields_by_index = load_goals_and_extra_fields_from_config(config)
    except Exception as exc:
        raise ValueError(f"Failed to load goals from dataset: {exc}") from exc

    return [
        Goal(
            text=text,
            index=index,
            labels={},
            extra=dict(extra_fields_by_index.get(index, {})),
        )
        for index, text in enumerate(texts)
    ]


__all__ = ["resolve_goals"]
