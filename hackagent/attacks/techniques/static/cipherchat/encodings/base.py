# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Common interface for CipherChat encoding strategies."""

from abc import ABC, abstractmethod

from .prompts import (
    BASELINE_SYSTEM_PROMPT,
    UNCHANGED_SYSTEM_PROMPT,
    UNICODE_SYSTEM_PROMPT,
)


class EncodeExpert(ABC):
    """A cipher: how to encipher and decipher text, and how to teach it.

    ``SYSTEM_PROMPT`` is the role prompt that tells the target it is an
    expert in this cipher; subclasses whose prompt depends on their settings
    override :meth:`system_prompt` instead.
    """

    SYSTEM_PROMPT = ""

    def system_prompt(self) -> str:
        """Return instructions describing this expert's encoding."""
        return self.SYSTEM_PROMPT

    @abstractmethod
    def encode(self, text: str) -> str:
        """Encode text using this expert's representation."""

    @abstractmethod
    def decode(self, text: str) -> str:
        """Decode text using this expert's representation."""


class IdentityExpert(EncodeExpert):
    """A "cipher" that leaves text as it is, for the plain-text settings."""

    def encode(self, text: str) -> str:
        """Return ``text`` unchanged."""
        return text

    def decode(self, text: str) -> str:
        """Return ``text`` unchanged."""
        return text


class BaselineExpert(IdentityExpert):
    """``baseline``: plain text under a neutral assistant system prompt."""

    SYSTEM_PROMPT = BASELINE_SYSTEM_PROMPT


class UnchangedExpert(IdentityExpert):
    """``unchange``: the paper's SelfCipher, a cipher role prompt over plain text."""

    SYSTEM_PROMPT = UNCHANGED_SYSTEM_PROMPT


class UnicodeExpert(EncodeExpert):
    """Unicode-escape strategy adapted from RobustNLP/CipherChat."""

    SYSTEM_PROMPT = UNICODE_SYSTEM_PROMPT

    def encode(self, text: str) -> str:
        """Write every character as a ``\\uXXXX`` escape."""
        return "".join(f"\\u{ord(character):04x}" for character in text)

    def decode(self, text: str) -> str:
        """Resolve the Unicode escapes in ``text``."""
        return text.encode("utf-8").decode("unicode_escape")
