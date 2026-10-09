# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The risk taxonomy goals are labelled with, read from ``taxonomy.yaml``.

Categories are letters (``E``), subcategories a letter and a number (``E2``).
A goal's labels pair them in display form, ``E. Cybersecurity Threats`` and
``E2. Exploit Development``; the category always follows from the
subcategory.
"""

from __future__ import annotations

import re
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

try:
    from enum import StrEnum
except ImportError:  # Python < 3.11

    class StrEnum(str, Enum):
        def __str__(self) -> str:
            return str(self.value)


PATH = Path(__file__).resolve().parent / "taxonomy.yaml"

UNCLASSIFIED = {
    "category": "Z. Unclassified Risk",
    "subcategory": "Z0. Unclassified Subcategory",
}


@lru_cache(maxsize=1)
def _tables() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Category labels, subcategory labels, and each subcategory's category."""
    raw = yaml.safe_load(PATH.read_text(encoding="utf-8"))
    categories: dict[str, str] = {}
    subcategories: dict[str, str] = {}
    parent: dict[str, str] = {}
    for category, entry in raw.items():
        categories[category] = entry["label"]
        for subcategory, label in entry["subcategories"].items():
            if not subcategory.startswith(category):
                raise ValueError(
                    f"{PATH.name}: {subcategory} is filed under {category}"
                )
            subcategories[subcategory] = label
            parent[subcategory] = category
    return categories, subcategories, parent


def categories() -> dict[str, str]:
    """Category code to label, in taxonomy order."""
    return dict(_tables()[0])


def subcategories(category: str | None = None) -> dict[str, str]:
    """Subcategory code to label, optionally only those of ``category``."""
    _, labels, parent = _tables()
    return {
        code: label
        for code, label in labels.items()
        if category is None or parent[code] == category
    }


def category_of(subcategory: str) -> str:
    return _tables()[2][subcategory]


def labels(subcategory: str) -> dict[str, str]:
    """A goal's labels for a subcategory code."""
    categories_, subcategories_, parent = _tables()
    category = parent[subcategory]
    return {
        "category": f"{category}. {categories_[category]}",
        "subcategory": f"{subcategory}. {subcategories_[subcategory]}",
    }


def describe() -> str:
    """The taxonomy as a model reads it: one code and label per line."""
    lines = []
    for code, label in categories().items():
        lines.append(f"{code}. {label}")
        lines.extend(f"- {sub}. {name}" for sub, name in subcategories(code).items())
    return "\n".join(lines)


def _key(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", value.upper())


def _resolve(value: Any, labels_: dict[str, str], code: str, kind: str) -> str:
    candidate = str(value.value if isinstance(value, Enum) else value)
    candidate = candidate.strip().strip("*`'\"").strip()
    upper = candidate.upper()
    if upper in labels_:
        return upper
    # A leading code wins: "E2. Exploit Development", "E2 - Exploit Development".
    prefix = re.match(rf"^({code})(?![A-Z0-9])", upper)
    if prefix and prefix.group(1) in labels_:
        return prefix.group(1)
    names = {_key(label): item for item, label in labels_.items()}
    plain = re.sub(rf"^{code}(?:\s*[.):\-]|\s)\s*", "", upper)
    for name in (_key(candidate), _key(plain)):
        if name in names:
            return names[name]
    raise ValueError(f"Unknown {kind}: {value}")


def resolve_category(value: Any) -> str:
    """A category's code from its code, label, or display form."""
    return _resolve(value, _tables()[0], "[A-Z]", "category")


def resolve_subcategory(value: Any) -> str:
    """A subcategory's code from its code, label, or display form."""
    return _resolve(value, _tables()[1], "[A-Z][0-9]+", "subcategory")


def _enum_name(label: str) -> str:
    name = re.sub(r"[^A-Z0-9]+", "_", label.upper()).strip("_") or "UNKNOWN"
    return f"V_{name}" if name[0].isdigit() else name


def _enum(name: str, labels_: dict[str, str]) -> type[StrEnum]:
    members: dict[str, str] = {}
    for code, label in labels_.items():
        key = _enum_name(label)
        if key in members and members[key] != label:
            key = f"{key}_{code}"
        members[key] = label
        members[code] = label
    return StrEnum(name, members)


#: Members by name (``CYBERSECURITY_THREATS``) and by code (``E``).
IntentCategory = _enum("IntentCategory", _tables()[0])
IntentSubcategory = _enum("IntentSubcategory", _tables()[1])


__all__ = [
    "IntentCategory",
    "IntentSubcategory",
    "UNCLASSIFIED",
    "categories",
    "category_of",
    "describe",
    "labels",
    "resolve_category",
    "resolve_subcategory",
    "subcategories",
]
