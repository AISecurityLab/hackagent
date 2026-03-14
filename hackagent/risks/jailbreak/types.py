# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Jailbreak sub-types."""

from enum import Enum


class JailbreakType(Enum):
    """Sub-types for Jailbreak."""

    ROLEPLAY = "roleplay"
    """Uses fictional scenarios or personas to bypass safety filters."""
    ENCODING = "encoding"
    """Encodes malicious intent via Base64, ROT13, leetspeak, etc."""

    MULTI_TURN = "multi_turn"
    """Gradually escalates across conversation turns (crescendo)."""

    HYPOTHETICAL = "hypothetical"
    """Frames harmful requests as hypothetical or academic questions."""

    AUTHORITY_MANIPULATION = "authority_manipulation"
    """Invokes false authority or urgency to override restrictions."""


JAILBREAK_TYPES = list(JailbreakType)
