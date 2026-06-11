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
"""

from .attack import MMLAttack

__all__ = ["MMLAttack"]
