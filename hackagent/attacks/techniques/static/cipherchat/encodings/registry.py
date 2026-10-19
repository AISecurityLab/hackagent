# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Factory registry for CipherChat encoding strategies."""

from .base import (
    BaselineExpert,
    EncodeExpert,
    UnchangedExpert,
    UnicodeExpert,
)
from .byte_escape import GBKExpert, UTF8Expert
from .mapping import (
    AsciiExpert,
    AtbashExpert,
    CaesarExpert,
    ChineseSubstitutionExpert,
    MorseExpert,
)

_EXPERT_TYPES: dict[str, type[EncodeExpert]] = {
    "unchange": UnchangedExpert,
    "baseline": BaselineExpert,
    "unicode": UnicodeExpert,
    "morse": MorseExpert,
    "atbash": AtbashExpert,
    "utf": UTF8Expert,
    "ascii": AsciiExpert,
    "gbk": GBKExpert,
    "selfdefine": ChineseSubstitutionExpert,
}
SUPPORTED_ENCODINGS = frozenset(
    [*_EXPERT_TYPES, *(f"caesar-{shift}" for shift in range(26))]
)


def create_encode_expert(
    encode_method: str,
) -> EncodeExpert:
    if encode_method not in SUPPORTED_ENCODINGS:
        supported = ", ".join(sorted(SUPPORTED_ENCODINGS))
        raise ValueError(
            f"Unsupported encode_method '{encode_method}'. Supported: {supported}"
        )

    if encode_method.startswith("caesar-"):
        return CaesarExpert(shift=int(encode_method.removeprefix("caesar-")))

    return _EXPERT_TYPES[encode_method]()
