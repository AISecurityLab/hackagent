# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Data types for threat-to-evaluation mapping.

Defines the dataclasses that map a vulnerability (threat) to the
datasets, attack techniques, objectives, and metrics needed to build
an evaluation campaign.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Type

from hackagent.risks.base import BaseVulnerability


# ── Relevance ────────────────────────────────────────────────────────


class Relevance(Enum):
    """How closely a dataset/attack matches a vulnerability."""

    PRIMARY = "primary"
    """Directly designed to test this vulnerability."""

    SECONDARY = "secondary"
    """Useful for broader coverage or baseline comparison."""


# ── Dataset recommendation ───────────────────────────────────────────


@dataclass(frozen=True)
class DatasetRecommendation:
    """Links a dataset preset to a vulnerability with a relevance tag.

    Parameters
    ----------
    preset : str
        Key in ``hackagent.datasets.presets.PRESETS`` (e.g. ``"advbench"``).
    relevance : Relevance
        How directly this dataset tests the vulnerability.
    rationale : str
        One-liner explaining *why* this dataset is relevant.
    """

    preset: str
    relevance: Relevance = Relevance.PRIMARY
    rationale: str = ""


# ── Attack recommendation ────────────────────────────────────────────


@dataclass(frozen=True)
class AttackRecommendation:
    """Links an attack technique to a vulnerability.

    Parameters
    ----------
    technique : str
        Key in ``hackagent.attacks.registry.ATTACK_REGISTRY``
        (e.g. ``"Baseline"``, ``"PAIR"``, ``"AdvPrefix"``).
    relevance : Relevance
        How well-suited this technique is for the vulnerability.
    rationale : str
        One-liner explaining *why* this technique applies.
    """

    technique: str
    relevance: Relevance = Relevance.PRIMARY
    rationale: str = ""


# ── Threat profile ───────────────────────────────────────────────────


@dataclass(frozen=True)
class ThreatProfile:
    """Complete evaluation mapping for a single vulnerability.

    A ``ThreatProfile`` answers the question:

        "Given vulnerability *X*, which datasets, attack techniques,
         objective, and metrics should an evaluation campaign use?"

    Parameters
    ----------
    vulnerability : type[BaseVulnerability]
        The vulnerability class this profile describes.
    datasets : list[DatasetRecommendation]
        Recommended datasets, ordered by relevance (primary first).
    attacks : list[AttackRecommendation]
        Compatible attack techniques.
    objective : str
        Default attack objective key (e.g. ``"jailbreak"``,
        ``"harmful_behavior"``, ``"policy_violation"``).
    metrics : list[str]
        Metric names relevant to this vulnerability
        (e.g. ``"asr"``, ``"toxicity_score"``, ``"judge_score"``).
    description : str
        Human-readable summary of what the profile evaluates.
    """

    vulnerability: Type[BaseVulnerability]
    datasets: List[DatasetRecommendation] = field(default_factory=list)
    attacks: List[AttackRecommendation] = field(default_factory=list)
    objective: str = "jailbreak"
    metrics: List[str] = field(default_factory=lambda: ["asr"])
    description: str = ""

    # ── Convenience helpers ──────────────────────────────────────────

    @property
    def name(self) -> str:
        """Vulnerability class name."""
        return self.vulnerability.name or self.vulnerability.__name__

    @property
    def primary_datasets(self) -> List[DatasetRecommendation]:
        """Return only primary-relevance datasets."""
        return [d for d in self.datasets if d.relevance is Relevance.PRIMARY]

    @property
    def secondary_datasets(self) -> List[DatasetRecommendation]:
        """Return only secondary-relevance datasets."""
        return [d for d in self.datasets if d.relevance is Relevance.SECONDARY]

    @property
    def primary_attacks(self) -> List[AttackRecommendation]:
        """Return only primary-relevance attacks."""
        return [a for a in self.attacks if a.relevance is Relevance.PRIMARY]

    @property
    def dataset_presets(self) -> List[str]:
        """Flat list of all recommended dataset preset keys."""
        return [d.preset for d in self.datasets]

    @property
    def attack_techniques(self) -> List[str]:
        """Flat list of all recommended attack technique keys."""
        return [a.technique for a in self.attacks]

    @property
    def has_datasets(self) -> bool:
        """True if at least one dataset is recommended."""
        return len(self.datasets) > 0
