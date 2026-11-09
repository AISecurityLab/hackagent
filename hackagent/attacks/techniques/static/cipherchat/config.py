# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration for CipherChat."""

from typing import Literal

from pydantic import Field, field_validator

from ..base import AttackParams
from .demonstrations import DEMONSTRATIONS
from .encodings import SUPPORTED_ENCODINGS


class CipherChatParams(AttackParams):
    """Cipher, demonstrations, and whether target replies are decoded.

    ``encode_method`` picks the cipher. ``use_system_role``,
    ``use_demonstrations``, ``demonstration_toxicity``, ``instruction_type``,
    ``language`` and ``num_demonstrations`` shape the system prompt that
    teaches it, and ``decode_response`` controls whether the reply is
    deciphered before judging. Validation rejects unknown ciphers and
    demonstration topics.
    """

    encode_method: str = Field(
        default="caesar-3",
        description=(
            "Cipher used to encode the conversation: caesar-0 to caesar-25, atbash,"
            " morse, ascii, unicode, utf, gbk, selfdefine, unchange (no cipher, "
            "role prompt only) or baseline (plain text). The target is told to "
            "reply in the same cipher."
        ),
    )
    use_system_role: bool = Field(
        default=True,
        description=(
            "Open the system prompt with the cipher's role prompt (\"You are an "
            'expert on ..."). When off it is left out; enciphered demonstrations '
            "are still sent as a system message."
        ),
    )
    use_demonstrations: bool = Field(
        default=True,
        description=(
            "Include example conversations written in the cipher, to teach the "
            "target the format. Ignored for the baseline method."
        ),
    )
    demonstration_toxicity: Literal["toxic", "harmless"] = Field(
        default="toxic",
        description=(
            "Whether the example conversations are toxic or harmless. Toxic "
            "examples push the target further toward unsafe replies; harmless ones"
            " exist only for Crimes_And_Illegal_Activities."
        ),
    )
    instruction_type: str = Field(
        default="Crimes_And_Illegal_Activities",
        description=(
            "Topic of the example conversations, e.g. Crimes_And_Illegal_Activities"
            " or Privacy_And_Property."
        ),
    )
    language: Literal["en", "zh"] = Field(
        default="en",
        description="Language of the examples: en (English) or zh (Chinese).",
    )
    num_demonstrations: int = Field(
        default=3, ge=0, description="How many example conversations to include."
    )
    decode_response: bool = Field(
        default=True,
        description="Decode the target's ciphered reply before the judges read it.",
    )

    @field_validator("encode_method")
    @classmethod
    def validate_encode_method(cls, value: str) -> str:
        """Reject a cipher not in :data:`~.encodings.SUPPORTED_ENCODINGS`."""
        if value not in SUPPORTED_ENCODINGS:
            supported = ", ".join(sorted(SUPPORTED_ENCODINGS))
            raise ValueError(
                f"Unsupported encode_method {value!r}. Supported: {supported}"
            )
        return value

    @field_validator("instruction_type")
    @classmethod
    def validate_instruction_type(cls, value: str) -> str:
        """Reject a topic with no demonstrations."""
        if value not in DEMONSTRATIONS:
            supported = ", ".join(sorted(DEMONSTRATIONS))
            raise ValueError(
                f"Unsupported instruction_type {value!r}. Supported: {supported}"
            )
        return value
