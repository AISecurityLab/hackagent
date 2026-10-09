# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""CipherChat encoding strategies."""

from .base import (
    BaselineExpert,
    EncodeExpert,
    IdentityExpert,
    UnchangedExpert,
    UnicodeExpert,
)
from .byte_escape import ByteEscapeExpert, GBKExpert, UTF8Expert
from .registry import SUPPORTED_ENCODINGS, create_encode_expert
from .mapping import (
    AsciiExpert,
    AtbashExpert,
    CaesarExpert,
    CharacterTranslationExpert,
    ChineseSubstitutionExpert,
    MappingExpert,
    MorseExpert,
    TokenExpert,
)

__all__ = [
    "SUPPORTED_ENCODINGS",
    "AsciiExpert",
    "AtbashExpert",
    "BaselineExpert",
    "ByteEscapeExpert",
    "CaesarExpert",
    "CharacterTranslationExpert",
    "ChineseSubstitutionExpert",
    "EncodeExpert",
    "GBKExpert",
    "IdentityExpert",
    "MappingExpert",
    "MorseExpert",
    "TokenExpert",
    "UTF8Expert",
    "UnchangedExpert",
    "UnicodeExpert",
    "create_encode_expert",
]
