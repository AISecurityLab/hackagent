# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Input Manipulation Attack sub-types."""

from enum import Enum


class InputManipulationAttackType(Enum):
    """Sub-types for Input Manipulation Attack."""

    ENCODING_BYPASS = "encoding_bypass"
    """Using character encoding tricks to bypass input filters."""
    FORMAT_STRING_ATTACK = "format_string_attack"
    """Exploiting format string processing in input handling."""

    UNICODE_MANIPULATION = "unicode_manipulation"
    """Using Unicode homoglyphs or special characters to evade detection."""


INPUT_MANIPULATION_ATTACK_TYPES = list(InputManipulationAttackType)
