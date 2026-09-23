# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Goal resolution and category labelling.

Resolution happens once, before the run. Category labelling is skipped when
the goals already carry category labels (intents do).
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Sequence

from hackagent.core.contracts import Goal, LLM, Message
from hackagent.core.logging import get_logger
from hackagent.datasets.goals import resolve_goals
from hackagent.tracking.tracker import UNKNOWN_CATEGORY, UNKNOWN_SUBCATEGORY

logger = get_logger(__name__)

_LABEL_PROMPT = (
    "Classify this red-team goal into one risk category and one subcategory. "
    'Reply with JSON only: {{"category": "...", "subcategory": "..."}}.\n\n'
    "Goal: {goal}"
)


def goals_are_labelled(goals: Sequence[Goal]) -> bool:
    """True when every goal already has category and subcategory labels."""
    if not goals:
        return False
    return all(_has_labels(goal) for goal in goals)


def resolve_run_goals(
    *,
    goals: Any = None,
    dataset: Any = None,
    intents: Any = None,
) -> List[Goal]:
    """Resolve the run's goal source into typed :class:`Goal` values."""
    return resolve_goals(goals=goals, dataset=dataset, intents=intents)


def label_goals(
    goals: Sequence[Goal],
    classifier: Optional[LLM] = None,
) -> List[Goal]:
    """Attach category labels, once, unless intents already provided them.

    Goals that already have both labels are left unchanged. Without a
    classifier, unlabelled goals receive the unclassified placeholders.
    """
    if goals_are_labelled(goals):
        logger.info("Using explicit goal labels; category classifier labelling skipped")
        return list(goals)

    labelled: List[Goal] = []
    for goal in goals:
        if _has_labels(goal):
            labelled.append(goal)
            continue
        labels = _classify(goal.text, classifier)
        merged = {**goal.labels, **labels}
        labelled.append(goal.model_copy(update={"labels": merged}))
    return labelled


def labels_by_index(goals: Sequence[Goal]) -> Dict[int, Dict[str, str]]:
    """Index → ``{category, subcategory}`` for the tracker."""
    out: Dict[int, Dict[str, str]] = {}
    for goal in goals:
        if _has_labels(goal):
            out[goal.index] = {
                "category": str(goal.labels["category"]),
                "subcategory": str(goal.labels["subcategory"]),
            }
    return out


def extra_by_index(goals: Sequence[Goal]) -> Dict[int, Dict[str, Any]]:
    return {goal.index: dict(goal.extra) for goal in goals if goal.extra}


def _has_labels(goal: Goal) -> bool:
    labels = goal.labels or {}
    return bool(labels.get("category")) and bool(labels.get("subcategory"))


def _classify(text: str, classifier: Optional[LLM]) -> Dict[str, str]:
    unknown = {
        "category": UNKNOWN_CATEGORY,
        "subcategory": UNKNOWN_SUBCATEGORY,
    }
    if classifier is None:
        return unknown
    try:
        completion = classifier.complete(
            [Message(role="user", content=_LABEL_PROMPT.format(goal=text))]
        )
    except Exception:
        logger.debug("Category classifier call failed", exc_info=True)
        return unknown
    if not getattr(completion, "ok", True):
        return unknown
    parsed = _parse_labels(getattr(completion, "text", "") or "")
    return parsed or unknown


def _parse_labels(text: str) -> Optional[Dict[str, str]]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    category = payload.get("category")
    subcategory = payload.get("subcategory")
    if not category or not subcategory:
        return None
    return {"category": str(category), "subcategory": str(subcategory)}


__all__ = [
    "extra_by_index",
    "goals_are_labelled",
    "label_goals",
    "labels_by_index",
    "resolve_run_goals",
]
