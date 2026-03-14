# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Shared shorthand helpers for building threat profiles.

These are intentionally private but shared across all threat profile modules.
"""

from __future__ import annotations

from typing import List

from hackagent.risks.profile_types import (
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
    atk("Baseline", PRIMARY, "Template-based prompt injection"),
    atk("PAIR", PRIMARY, "Iterative refinement for bypass discovery"),
    atk("AdvPrefix", SECONDARY, "Adversarial prefix optimisation"),
]

BASELINE_ONLY: List[AttackRecommendation] = [
    atk("Baseline", PRIMARY, "Template-based prompt construction"),
]

ALL_ATTACKS: List[AttackRecommendation] = [
    atk("Baseline", PRIMARY, "Template-based attack"),
    atk("PAIR", PRIMARY, "Iterative refinement"),
    atk("AdvPrefix", PRIMARY, "Adversarial prefix optimisation"),
]
