# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Intent taxonomy helpers backed by the OmniSafeBench dataset.

This module exposes enum-like category/subcategory values and utilities to
select goal samples directly from taxonomy labels.
"""

from __future__ import annotations

import json
import re
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

try:
    from enum import StrEnum
except ImportError:  # Python < 3.11

    class StrEnum(str, Enum):
        """Minimal StrEnum fallback for Python 3.10 compatibility."""

        pass


_OMNISAFEBENCH_DATASET_PATH = (
    Path(__file__).resolve().parent / "omnisafebench" / "dataset.json"
)


def _normalize_lookup(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", (value or "").upper()).strip()


def _to_enum_name(label: str) -> str:
    normalized = re.sub(r"[^A-Z0-9]+", "_", (label or "").upper()).strip("_")
    if not normalized:
        return "UNKNOWN"
    if normalized[0].isdigit():
        return f"V_{normalized}"
    return normalized


@lru_cache(maxsize=1)
def _load_raw_taxonomy() -> Dict[str, Any]:
    with _OMNISAFEBENCH_DATASET_PATH.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)
    if not isinstance(payload, dict):
        raise ValueError("OmniSafeBench taxonomy file must contain a JSON object")
    return payload


@lru_cache(maxsize=1)
def _taxonomy_maps() -> Dict[str, Any]:
    raw = _load_raw_taxonomy()

    category_code_to_label: Dict[str, str] = {}
    subcategory_code_to_label: Dict[str, str] = {}
    category_to_subcategories: Dict[str, List[str]] = {}
    subcategory_to_category: Dict[str, str] = {}
    intents_by_subcategory: Dict[str, List[str]] = {}

    for category_code, category_payload in raw.items():
        if not isinstance(category_payload, dict):
            continue

        category_label = str(category_payload.get("label") or "").strip()
        if not category_label:
            continue

        normalized_category_code = str(category_code).strip().upper()
        category_code_to_label[normalized_category_code] = category_label
        category_to_subcategories[normalized_category_code] = []

        subcategories = category_payload.get("subcategories") or {}
        if not isinstance(subcategories, dict):
            continue

        for subcategory_code, subcategory_payload in subcategories.items():
            if not isinstance(subcategory_payload, dict):
                continue

            subcategory_label = str(subcategory_payload.get("label") or "").strip()
            if not subcategory_label:
                continue

            normalized_subcategory_code = str(subcategory_code).strip().upper()
            subcategory_code_to_label[normalized_subcategory_code] = subcategory_label
            category_to_subcategories[normalized_category_code].append(
                normalized_subcategory_code
            )
            subcategory_to_category[normalized_subcategory_code] = (
                normalized_category_code
            )

            intents = subcategory_payload.get("intents") or []
            if not isinstance(intents, list):
                intents = []

            cleaned_intents = [
                str(intent).strip()
                for intent in intents
                if isinstance(intent, str) and str(intent).strip()
            ]
            intents_by_subcategory[normalized_subcategory_code] = cleaned_intents

    category_plain_name_to_code = {
        _normalize_lookup(label): code for code, label in category_code_to_label.items()
    }
    subcategory_plain_name_to_code = {
        _normalize_lookup(label): code
        for code, label in subcategory_code_to_label.items()
    }

    return {
        "category_code_to_label": category_code_to_label,
        "subcategory_code_to_label": subcategory_code_to_label,
        "category_to_subcategories": category_to_subcategories,
        "subcategory_to_category": subcategory_to_category,
        "intents_by_subcategory": intents_by_subcategory,
        "category_plain_name_to_code": category_plain_name_to_code,
        "subcategory_plain_name_to_code": subcategory_plain_name_to_code,
    }


def _build_category_enum() -> type[StrEnum]:
    category_code_to_label = _taxonomy_maps()["category_code_to_label"]
    members: Dict[str, str] = {}

    for code, label in category_code_to_label.items():
        enum_name = _to_enum_name(label)
        if enum_name in members and members[enum_name] != label:
            enum_name = f"{enum_name}_{code}"
        members[enum_name] = label
        members[code] = label

    return StrEnum("IntentCategory", members)


def _build_subcategory_enum() -> type[StrEnum]:
    subcategory_code_to_label = _taxonomy_maps()["subcategory_code_to_label"]
    members: Dict[str, str] = {}

    for code, label in subcategory_code_to_label.items():
        enum_name = _to_enum_name(label)
        if enum_name in members and members[enum_name] != label:
            enum_name = f"{enum_name}_{code}"
        members[enum_name] = label
        members[code] = label

    return StrEnum("IntentSubcategory", members)


IntentCategory = _build_category_enum()
IntentSubcategory = _build_subcategory_enum()


def _resolve_category_code(value: Any) -> str:
    maps = _taxonomy_maps()
    category_code_to_label: Mapping[str, str] = maps["category_code_to_label"]
    category_plain_name_to_code: Mapping[str, str] = maps["category_plain_name_to_code"]

    candidate = str(value).strip()
    if not candidate:
        raise ValueError("Intent category cannot be empty")

    upper_candidate = candidate.upper()
    if upper_candidate in category_code_to_label:
        return upper_candidate

    code_match = re.match(r"^([A-Z])(?:\b|[\s\.-])", upper_candidate)
    if code_match and code_match.group(1) in category_code_to_label:
        return code_match.group(1)

    plain_code = category_plain_name_to_code.get(_normalize_lookup(candidate))
    if plain_code:
        return plain_code

    raise ValueError(f"Unknown intent category: {value}")


def _resolve_subcategory_code(value: Any) -> str:
    maps = _taxonomy_maps()
    subcategory_code_to_label: Mapping[str, str] = maps["subcategory_code_to_label"]
    subcategory_plain_name_to_code: Mapping[str, str] = maps[
        "subcategory_plain_name_to_code"
    ]

    candidate = str(value).strip()
    if not candidate:
        raise ValueError("Intent subcategory cannot be empty")

    upper_candidate = candidate.upper()
    if upper_candidate in subcategory_code_to_label:
        return upper_candidate

    code_match = re.match(r"^([A-Z][0-9]+)(?:\b|[\s\.-])", upper_candidate)
    if code_match and code_match.group(1) in subcategory_code_to_label:
        return code_match.group(1)

    plain_code = subcategory_plain_name_to_code.get(_normalize_lookup(candidate))
    if plain_code:
        return plain_code

    raise ValueError(f"Unknown intent subcategory: {value}")


def _coerce_intent_entries(intents_config: Any) -> Sequence[Mapping[str, Any]]:
    if isinstance(intents_config, list):
        entries = intents_config
    elif isinstance(intents_config, dict):
        if isinstance(intents_config.get("intents"), list):
            entries = intents_config["intents"]
        elif isinstance(intents_config.get("selections"), list):
            entries = intents_config["selections"]
        elif isinstance(intents_config.get("items"), list):
            entries = intents_config["items"]
        elif "category" in intents_config:
            entries = [intents_config]
        else:
            raise ValueError(
                "'intents' must be a list of objects or an object with "
                "'intents'/'selections'/'items'."
            )
    else:
        raise ValueError("'intents' must be a list or a dictionary")

    if not entries:
        raise ValueError("'intents' configuration is empty")

    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Each intents entry must be an object")
    return entries


def load_goals_from_intents_config(
    intents_config: Any,
) -> Tuple[List[str], Dict[int, Dict[str, str]]]:
    """Resolve an intents selection config to goals plus explicit labels.

    Returns:
        Tuple where:
        - index 0 is the selected goals list.
        - index 1 maps goal index -> {"category": ..., "subcategory": ...}
          using the same label format produced by the category classifier
          parser (``X. Label`` / ``Xn. Label``).
    """

    maps = _taxonomy_maps()
    category_code_to_label: Mapping[str, str] = maps["category_code_to_label"]
    subcategory_code_to_label: Mapping[str, str] = maps["subcategory_code_to_label"]
    category_to_subcategories: Mapping[str, List[str]] = maps[
        "category_to_subcategories"
    ]
    subcategory_to_category: Mapping[str, str] = maps["subcategory_to_category"]
    intents_by_subcategory: Mapping[str, List[str]] = maps["intents_by_subcategory"]

    entries = _coerce_intent_entries(intents_config)

    goals: List[str] = []
    labels_by_index: Dict[int, Dict[str, str]] = {}

    for entry in entries:
        category_value = entry.get("category")
        if category_value is None:
            raise ValueError("Each intents entry must include 'category'")

        category_code = _resolve_category_code(category_value)

        raw_subcategories = entry.get("subcategories")
        if raw_subcategories is None:
            selected_subcategories = list(
                category_to_subcategories.get(category_code, [])
            )
        else:
            if not isinstance(raw_subcategories, list):
                raise ValueError("'subcategories' must be a list when provided")

            selected_subcategories = []
            for subcategory_value in raw_subcategories:
                subcategory_code = _resolve_subcategory_code(subcategory_value)
                owner_category = subcategory_to_category.get(subcategory_code)
                if owner_category != category_code:
                    raise ValueError(
                        f"Subcategory {subcategory_value} does not belong to category {category_value}"
                    )
                selected_subcategories.append(subcategory_code)

        if not selected_subcategories:
            raise ValueError(
                f"No subcategories found for category {category_value} in intents config"
            )

        raw_samples = entry.get("samples_per_subcategory", 1)
        try:
            samples_per_subcategory = int(raw_samples)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "'samples_per_subcategory' must be a positive integer"
            ) from exc
        if samples_per_subcategory <= 0:
            raise ValueError("'samples_per_subcategory' must be >= 1")

        category_label = category_code_to_label[category_code]
        formatted_category = f"{category_code}. {category_label}"

        for subcategory_code in selected_subcategories:
            subcategory_label = subcategory_code_to_label[subcategory_code]
            formatted_subcategory = f"{subcategory_code}. {subcategory_label}"

            available_intents = intents_by_subcategory.get(subcategory_code, [])
            if not available_intents:
                raise ValueError(
                    f"No intents available for subcategory {formatted_subcategory}"
                )

            selected = available_intents[:samples_per_subcategory]
            for intent in selected:
                goal_index = len(goals)
                goals.append(intent)
                labels_by_index[goal_index] = {
                    "category": formatted_category,
                    "subcategory": formatted_subcategory,
                }

    if not goals:
        raise ValueError("No goals selected from intents configuration")

    return goals, labels_by_index


__all__ = [
    "IntentCategory",
    "IntentSubcategory",
    "load_goals_from_intents_config",
]
