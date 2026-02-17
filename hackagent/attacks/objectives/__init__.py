# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Attack objectives module.

Objectives define WHAT vulnerabilities we're testing for.
Each objective provides:
- Success/failure patterns
- Evaluation criteria for judges
- Objective-specific context

Note: Objectives are metadata/config, not execution classes.

Available objectives:
- JAILBREAK: Bypass safety guardrails
- HARMFUL_BEHAVIOR: Elicit harmful content
- POLICY_VIOLATION: Cause policy violations with multi-criteria assessment
"""

from .base import ObjectiveConfig
from .jailbreak import JAILBREAK, REFUSAL_PATTERNS as JAILBREAK_REFUSAL_PATTERNS
from .harmful_behavior import HARMFUL_BEHAVIOR
from .policy_violation import POLICY_VIOLATION

# Registry for easy lookup
OBJECTIVES = {
    "jailbreak": JAILBREAK,
    "harmful_behavior": HARMFUL_BEHAVIOR,
    "policy_violation": POLICY_VIOLATION,
}

__all__ = [
    "ObjectiveConfig",
    "JAILBREAK",
    "HARMFUL_BEHAVIOR",
    "POLICY_VIOLATION",
    "OBJECTIVES",
    "JAILBREAK_REFUSAL_PATTERNS",
]
