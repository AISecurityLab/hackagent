# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Select goals from the OmniSafeBench intents by taxonomy category.

Each selected intent becomes a goal already labelled with the category and
subcategory it is filed under, so it needs no classifier.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from hackagent.datasets import taxonomy
from hackagent.datasets.taxonomy import IntentCategory, IntentSubcategory

_OMNISAFEBENCH = Path(__file__).resolve().parent / "omnisafebench" / "dataset.json"


@lru_cache(maxsize=1)
def _omnisafebench() -> dict[str, Any]:
    return json.loads(_OMNISAFEBENCH.read_text(encoding="utf-8"))


def intents_of(subcategory: str) -> tuple[str, ...]:
    """The OmniSafeBench intents filed under a taxonomy subcategory."""
    filed = _omnisafebench().get(taxonomy.category_of(subcategory), {})
    intents = (filed.get("subcategories") or {}).get(subcategory, {}).get("intents")
    return tuple(
        text.strip() for text in intents or [] if isinstance(text, str) and text.strip()
    )


def _coerce_intent_entries(intents_config: Any) -> Sequence[Mapping[str, Any]]:
    if isinstance(intents_config, list):
        entries = intents_config
    elif isinstance(intents_config, dict):
        for key in ("intents", "selections", "items"):
            if isinstance(intents_config.get(key), list):
                entries = intents_config[key]
                break
        else:
            if "category" not in intents_config:
                raise ValueError(
                    "'intents' must be a list of objects or an object with "
                    "'intents'/'selections'/'items'."
                )
            entries = [intents_config]
    else:
        raise ValueError("'intents' must be a list or a dictionary")

    if not entries:
        raise ValueError("'intents' configuration is empty")
    if not all(isinstance(entry, dict) for entry in entries):
        raise ValueError("Each intents entry must be an object")
    return entries


def load_goals_from_intents_config(
    intents_config: Any,
) -> Tuple[List[str], Dict[int, Dict[str, str]]]:
    """Resolve an intents selection to goals and each goal's labels."""
    goals: List[str] = []
    labels_by_index: Dict[int, Dict[str, str]] = {}

    for entry in _coerce_intent_entries(intents_config):
        category_value = entry.get("category")
        if category_value is None:
            raise ValueError("Each intents entry must include 'category'")
        category = taxonomy.resolve_category(category_value)

        raw_subcategories = entry.get("subcategories")
        if raw_subcategories is None:
            selected = list(taxonomy.subcategories(category))
        elif not isinstance(raw_subcategories, list):
            raise ValueError("'subcategories' must be a list when provided")
        else:
            selected = []
            for value in raw_subcategories:
                subcategory = taxonomy.resolve_subcategory(value)
                if taxonomy.category_of(subcategory) != category:
                    raise ValueError(
                        f"Subcategory {value} does not belong to category {category_value}"
                    )
                selected.append(subcategory)
        if not selected:
            raise ValueError(
                f"No subcategories found for category {category_value} in intents config"
            )

        try:
            per_subcategory = int(entry.get("samples_per_subcategory", 1))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "'samples_per_subcategory' must be a positive integer"
            ) from exc
        if per_subcategory <= 0:
            raise ValueError("'samples_per_subcategory' must be >= 1")

        for subcategory in selected:
            intents = intents_of(subcategory)
            if not intents:
                raise ValueError(f"No intents available for subcategory {subcategory}")
            for intent in intents[:per_subcategory]:
                labels_by_index[len(goals)] = taxonomy.labels(subcategory)
                goals.append(intent)

    if not goals:
        raise ValueError("No goals selected from intents configuration")
    return goals, labels_by_index


__all__ = [
    "IntentCategory",
    "IntentSubcategory",
    "intents_of",
    "load_goals_from_intents_config",
]
