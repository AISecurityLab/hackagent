# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Attack objectives: what vulnerability a run is testing for."""

from hackagent.attacks._lib.objectives.base import ObjectiveConfig
from hackagent.attacks._lib.objectives.harmful_behavior import HARMFUL_BEHAVIOR
from hackagent.attacks._lib.objectives.jailbreak import (
    JAILBREAK,
    REFUSAL_PATTERNS as JAILBREAK_REFUSAL_PATTERNS,
)
from hackagent.attacks._lib.objectives.policy_violation import POLICY_VIOLATION
from hackagent.attacks._lib.objectives.rag import RAG

OBJECTIVES = {
    "jailbreak": JAILBREAK,
    "harmful_behavior": HARMFUL_BEHAVIOR,
    "policy_violation": POLICY_VIOLATION,
    "rag": RAG,
}

__all__ = [
    "ObjectiveConfig",
    "JAILBREAK",
    "HARMFUL_BEHAVIOR",
    "POLICY_VIOLATION",
    "RAG",
    "OBJECTIVES",
    "JAILBREAK_REFUSAL_PATTERNS",
]
