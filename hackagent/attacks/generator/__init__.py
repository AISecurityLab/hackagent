# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Compatibility shim — prefer ``hackagent.attacks._lib.templates``."""

from hackagent.attacks._lib.templates import (
    REFUSAL_PATTERNS,
    SUCCESS_PATTERNS,
    AttackTemplates,
)

__all__ = [
    "AttackTemplates",
    "REFUSAL_PATTERNS",
    "SUCCESS_PATTERNS",
]
