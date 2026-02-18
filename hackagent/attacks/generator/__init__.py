# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Generator module for attack prompt generation.

This package provides reusable prompt templates and generation
utilities used across different attack techniques.

Modules:
    templates: Attack prompt template library and pattern constants

Usage:
    from hackagent.attacks.generator import (
        AttackTemplates,
        REFUSAL_PATTERNS,
        SUCCESS_PATTERNS,
    )
"""

from hackagent.attacks.generator.templates import (
    REFUSAL_PATTERNS,
    SUCCESS_PATTERNS,
    AttackTemplates,
)

__all__ = [
    "AttackTemplates",
    "REFUSAL_PATTERNS",
    "SUCCESS_PATTERNS",
]
