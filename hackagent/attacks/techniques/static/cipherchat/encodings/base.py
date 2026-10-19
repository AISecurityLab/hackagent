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
    def encode(self, text: str) -> str:
        return text

    def decode(self, text: str) -> str:
        return text


class BaselineExpert(IdentityExpert):
    SYSTEM_PROMPT = BASELINE_SYSTEM_PROMPT


class UnchangedExpert(IdentityExpert):
    SYSTEM_PROMPT = UNCHANGED_SYSTEM_PROMPT


class UnicodeExpert(EncodeExpert):
    """Unicode-escape strategy adapted from RobustNLP/CipherChat."""

    SYSTEM_PROMPT = UNICODE_SYSTEM_PROMPT

    def encode(self, text: str) -> str:
        return "".join(f"\\u{ord(character):04x}" for character in text)

    def decode(self, text: str) -> str:
        return text.encode("utf-8").decode("unicode_escape")
