# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
hackagent.risks — Vulnerability definitions and threat profiles.

This package organizes 13 cybersecurity vulnerabilities for AI systems.
Each subdirectory corresponds to a vulnerability and contains:
- types.py              — Enum of vulnerability sub-types
- vulnerabilities.py    — Concrete BaseVulnerability subclass
- profile.py            — Threat profile with datasets, attacks, metrics
"""

# Core base class
from hackagent.risks.base import BaseVulnerability

# Registry and helpers
from hackagent.risks.registry import (
    VULNERABILITY_REGISTRY,
    get_all_vulnerability_names,
    # All 13 vulnerabilities
    ModelEvasion,
    CraftAdversarialData,
    PromptInjection,
    Jailbreak,
    VectorEmbeddingWeaknessesExploit,
    SensitiveInformationDisclosure,
    SystemPromptLeakage,
    ExcessiveAgency,
    InputManipulationAttack,
    PublicFacingApplicationExploitation,
    MaliciousToolInvocation,
    CredentialExposure,
    Misinformation,
)

# Profile types
from hackagent.risks.profile_types import (
    ThreatProfile,
    DatasetRecommendation,
    AttackRecommendation,
    Relevance,
)

# Prompt injection template
from hackagent.risks.prompt_injection import PromptInjectionTemplate

__all__ = [
    # Core
    "BaseVulnerability",
    # Registry
    "VULNERABILITY_REGISTRY",
    "get_all_vulnerability_names",
    # Vulnerabilities
    "ModelEvasion",
    "CraftAdversarialData",
    "PromptInjection",
    "Jailbreak",
    "VectorEmbeddingWeaknessesExploit",
    "SensitiveInformationDisclosure",
    "SystemPromptLeakage",
    "ExcessiveAgency",
    "InputManipulationAttack",
    "PublicFacingApplicationExploitation",
    "MaliciousToolInvocation",
    "CredentialExposure",
    "Misinformation",
    # Templates
    "PromptInjectionTemplate",
    # Profile types
    "ThreatProfile",
    "DatasetRecommendation",
    "AttackRecommendation",
    "Relevance",
]
