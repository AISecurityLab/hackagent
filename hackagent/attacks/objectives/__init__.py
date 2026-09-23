# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Compatibility shim — prefer ``hackagent.attacks._lib.objectives``."""

from hackagent.attacks._lib.objectives import (
    HARMFUL_BEHAVIOR,
    JAILBREAK,
    JAILBREAK_REFUSAL_PATTERNS,
    OBJECTIVES,
    POLICY_VIOLATION,
    ObjectiveConfig,
)

__all__ = [
    "ObjectiveConfig",
    "JAILBREAK",
    "HARMFUL_BEHAVIOR",
    "POLICY_VIOLATION",
    "OBJECTIVES",
    "JAILBREAK_REFUSAL_PATTERNS",
]
