# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Official attack-category taxonomy for HackAgent.

Primary category (exactly one per attack) describes **how the target is hit**:

* :attr:`AttackCategory.STATIC` — one (or a few) fixed transforms, with no
  attacker refinement loop.
* :attr:`AttackCategory.ADAPTIVE` — many independent attempts that refine or
  search (no shared growing conversation).
* :attr:`AttackCategory.MULTI_TURN` — one growing conversation with the target.

Tags are orthogonal labels (zero or more), not extra top-level categories:

* :attr:`AttackTag.MULTIMODAL` — VLM / image attacks.
* :attr:`AttackTag.INDIRECT` / :attr:`AttackTag.RAG` — document poisoning and
  other indirect injection.

This module is the **single source of truth**. TUI specs, CLI catalog/help,
planner metadata, and docs should look up category and tags here rather than
hardcoding lists.

To add a new attack, give it exactly one :class:`AttackCategory` in
:data:`ATTACK_TAXONOMY` and any applicable :class:`AttackTag` values.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, Mapping, Optional, Tuple


class AttackCategory(str, Enum):
    """How an attack hits the target. Exactly one per technique."""

    STATIC = "static"
    ADAPTIVE = "adaptive"
    MULTI_TURN = "multi_turn"

    @property
    def label(self) -> str:
        """Human-readable heading used in CLI, TUI, and docs."""
        return {
            AttackCategory.STATIC: "Static",
            AttackCategory.ADAPTIVE: "Adaptive",
            AttackCategory.MULTI_TURN: "Multi-turn",
        }[self]

    @property
    def description(self) -> str:
        """One-line definition of this primary category."""
        return {
            AttackCategory.STATIC: (
                "One (or a few) fixed transforms, with no attacker refinement loop."
            ),
            AttackCategory.ADAPTIVE: (
                "Many independent attempts that refine or search, without a "
                "shared growing conversation."
            ),
            AttackCategory.MULTI_TURN: ("One growing conversation with the target."),
        }[self]


class AttackTag(str, Enum):
    """Orthogonal labels. An attack may have zero or more tags."""

    MULTIMODAL = "multimodal"
    INDIRECT = "indirect"
    RAG = "rag"

    @property
    def label(self) -> str:
        """Human-readable tag name."""
        return {
            AttackTag.MULTIMODAL: "Multimodal",
            AttackTag.INDIRECT: "Indirect",
            AttackTag.RAG: "RAG",
        }[self]


@dataclass(frozen=True)
class AttackTaxonomy:
    """Category and tags for one attack technique."""

    category: AttackCategory
    tags: Tuple[AttackTag, ...] = ()

    def tag_values(self) -> Tuple[str, ...]:
        """Return tag enum values in declaration order."""
        return tuple(tag.value for tag in self.tags)


def normalize_attack_type(technique_key: str) -> str:
    """Canonical lowercase ``attack_type`` key (``static-template`` → ``static_template``)."""
    return technique_key.strip().lower().replace("-", "_")


def _entry(category: AttackCategory, *tags: AttackTag) -> AttackTaxonomy:
    return AttackTaxonomy(category=category, tags=tags)


# Insertion order is the preferred listing order within each category.
ATTACK_TAXONOMY: Mapping[str, AttackTaxonomy] = {
    # Static — fixed transforms, no attacker refinement loop.
    "baseline": _entry(AttackCategory.STATIC),
    "static_template": _entry(AttackCategory.STATIC),
    "flipattack": _entry(AttackCategory.STATIC),
    "cipherchat": _entry(AttackCategory.STATIC),
    "h4rm3l": _entry(AttackCategory.STATIC),
    "mml": _entry(AttackCategory.STATIC, AttackTag.MULTIMODAL),
    "fc": _entry(AttackCategory.STATIC, AttackTag.MULTIMODAL),
    "tfc": _entry(AttackCategory.STATIC),
    "rag": _entry(AttackCategory.STATIC, AttackTag.INDIRECT, AttackTag.RAG),
    # Adaptive — independent refine/search attempts.
    "pair": _entry(AttackCategory.ADAPTIVE),
    "tap": _entry(AttackCategory.ADAPTIVE),
    "pap": _entry(AttackCategory.ADAPTIVE),
    "bon": _entry(AttackCategory.ADAPTIVE),
    "advprefix": _entry(AttackCategory.ADAPTIVE),
    "autodan_turbo": _entry(AttackCategory.ADAPTIVE),
    # Multi-turn — one growing conversation with the target.
    "crescendo": _entry(AttackCategory.MULTI_TURN),
}


def get_attack_taxonomy(technique_key: str) -> AttackTaxonomy:
    """Return the taxonomy entry for *technique_key*.

    Raises:
        KeyError: If the technique has not been assigned a primary category.
    """
    key = normalize_attack_type(technique_key)
    try:
        return ATTACK_TAXONOMY[key]
    except KeyError as exc:
        allowed = ", ".join(category.value for category in AttackCategory)
        raise KeyError(
            f"Attack {technique_key!r} has no taxonomy entry. Assign exactly "
            f"one primary category ({allowed}) in "
            "hackagent.attacks.taxonomy.ATTACK_TAXONOMY."
        ) from exc


def try_get_attack_taxonomy(technique_key: str) -> Optional[AttackTaxonomy]:
    """Return the taxonomy entry for *technique_key*, or ``None`` if unknown."""
    return ATTACK_TAXONOMY.get(normalize_attack_type(technique_key))


def attacks_for_category(category: AttackCategory) -> Tuple[str, ...]:
    """Return technique keys assigned to *category*, in registry order."""
    return tuple(
        key for key, entry in ATTACK_TAXONOMY.items() if entry.category is category
    )


def attacks_with_tag(tag: AttackTag) -> Tuple[str, ...]:
    """Return technique keys that carry *tag*, in registry order."""
    return tuple(key for key, entry in ATTACK_TAXONOMY.items() if tag in entry.tags)


def grouped_attack_keys(
    technique_keys: Optional[Iterable[str]] = None,
) -> Dict[AttackCategory, Tuple[str, ...]]:
    """Group *technique_keys* by primary category.

    Unknown keys are omitted. When *technique_keys* is ``None``, every
    registered technique is included. Within each category, the original
    iterable order is preserved (taxonomy insertion order when grouping all).
    """
    if technique_keys is None:
        keys = tuple(ATTACK_TAXONOMY)
    else:
        keys = tuple(normalize_attack_type(key) for key in technique_keys)

    grouped: Dict[AttackCategory, Tuple[str, ...]] = {
        category: () for category in AttackCategory
    }
    for key in keys:
        entry = try_get_attack_taxonomy(key)
        if entry is None:
            continue
        grouped[entry.category] = grouped[entry.category] + (key,)
    return grouped
