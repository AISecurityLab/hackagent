# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Vulnerability registry.

Central catalogue of every built-in vulnerability. Each vulnerability
lives in its own folder under ``risks/``.

To add a new vulnerability:
1. Create a new folder under ``risks/`` (e.g. ``my_vulnerability/``)
2. Implement ``types.py`` and ``vulnerabilities.py``
3. Import and register it here
"""

from typing import Dict, List, Type

from hackagent.risks.base import BaseVulnerability

from hackagent.risks.model_evasion import ModelEvasion

from hackagent.risks.craft_adversarial_data import CraftAdversarialData

from hackagent.risks.prompt_injection import PromptInjection

from hackagent.risks.jailbreak import Jailbreak

from hackagent.risks.vector_embedding_weaknesses_exploit import (
    VectorEmbeddingWeaknessesExploit,
)

from hackagent.risks.sensitive_information_disclosure import (
    SensitiveInformationDisclosure,
)

from hackagent.risks.system_prompt_leakage import SystemPromptLeakage

from hackagent.risks.excessive_agency import ExcessiveAgency

from hackagent.risks.input_manipulation_attack import InputManipulationAttack

from hackagent.risks.public_facing_application_exploitation import (
    PublicFacingApplicationExploitation,
)

from hackagent.risks.malicious_tool_invocation import MaliciousToolInvocation

from hackagent.risks.credential_exposure import CredentialExposure

from hackagent.risks.misinformation import Misinformation


# =====================================================================
# VULNERABILITY_REGISTRY  —  name → class
# =====================================================================

VULNERABILITY_REGISTRY: Dict[str, Type[BaseVulnerability]] = {
    "ModelEvasion": ModelEvasion,
    "CraftAdversarialData": CraftAdversarialData,
    "PromptInjection": PromptInjection,
    "Jailbreak": Jailbreak,
    "VectorEmbeddingWeaknessesExploit": VectorEmbeddingWeaknessesExploit,
    "SensitiveInformationDisclosure": SensitiveInformationDisclosure,
    "SystemPromptLeakage": SystemPromptLeakage,
    "ExcessiveAgency": ExcessiveAgency,
    "InputManipulationAttack": InputManipulationAttack,
    "PublicFacingApplicationExploitation": PublicFacingApplicationExploitation,
    "MaliciousToolInvocation": MaliciousToolInvocation,
    "CredentialExposure": CredentialExposure,
    "Misinformation": Misinformation,
}


# =====================================================================
# Helpers
# =====================================================================


def get_all_vulnerability_names() -> List[str]:
    """Return all registered vulnerability names."""
    return list(VULNERABILITY_REGISTRY.keys())


__all__ = [
    "VULNERABILITY_REGISTRY",
    "get_all_vulnerability_names",
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
]
