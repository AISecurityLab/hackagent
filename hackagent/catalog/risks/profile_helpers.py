# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Shared shorthand helpers for building threat profiles.

These are intentionally private but shared across all threat profile modules.
"""

from __future__ import annotations

from typing import List

from hackagent.catalog.risks.profile_types import (
    AttackRecommendation,
    DatasetRecommendation,
    Relevance,
)

# Shorthand constructors

PRIMARY = Relevance.PRIMARY
SECONDARY = Relevance.SECONDARY


def ds(
    preset: str,
    relevance: Relevance = PRIMARY,
    rationale: str = "",
) -> DatasetRecommendation:
    """Create a DatasetRecommendation."""
    return DatasetRecommendation(
        preset=preset,
        relevance=relevance,
        rationale=rationale,
    )


def atk(
    technique: str,
    relevance: Relevance = PRIMARY,
    rationale: str = "",
) -> AttackRecommendation:
    """Create an AttackRecommendation."""
    return AttackRecommendation(
        technique=technique,
        relevance=relevance,
        rationale=rationale,
    )


# Standard attack combos

JAILBREAK_ATTACKS: List[AttackRecommendation] = [
    atk("static_template", PRIMARY, "Template-based prompt injection"),
    atk("pair", PRIMARY, "Iterative refinement for bypass discovery"),
    atk("advprefix", SECONDARY, "Adversarial prefix optimisation"),
]

STATIC_TEMPLATE_ONLY: List[AttackRecommendation] = [
    atk("static_template", PRIMARY, "Template-based prompt construction"),
]

ALL_ATTACKS: List[AttackRecommendation] = [
    atk("static_template", PRIMARY, "Template-based attack"),
    atk("pair", PRIMARY, "Iterative refinement"),
    atk("advprefix", PRIMARY, "Adversarial prefix optimisation"),
]
