# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
MML (Multi-Modal Linkage) attack technique.

A multimodal jailbreak attack that encodes harmful prompts into images
using various visual transformations, then instructs a Vision-Language
Model to decode and act on the embedded content.

Reference: Wang et al., "Jailbreak Large Vision-Language Models Through
Multi-Modal Linkage" (2024)
https://arxiv.org/abs/2412.00473

Importing this package does not import the attack implementation. The CLI
catalog loads ``mml.config`` while registering commands, and the attack
module imports Pillow, which ships in the ``vision`` extra.
"""

from typing import Any

__all__ = ["MMLAttack"]


def __getattr__(name: str) -> Any:
    if name == "MMLAttack":
        from .attack import MMLAttack

        globals()["MMLAttack"] = MMLAttack
        return MMLAttack
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
