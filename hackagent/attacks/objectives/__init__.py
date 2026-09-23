# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Compatibility shim — prefer ``hackagent.attacks._lib.objectives``."""

from hackagent.attacks._lib.objectives import *  # noqa: F403
from hackagent.attacks._lib.objectives import OBJECTIVES  # noqa: F401

__all__ = [
    "ObjectiveConfig",
    "JAILBREAK",
    "HARMFUL_BEHAVIOR",
    "POLICY_VIOLATION",
    "OBJECTIVES",
    "JAILBREAK_REFUSAL_PATTERNS",
]
