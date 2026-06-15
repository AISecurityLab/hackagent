# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
FC-Attack (FlowChart Attack) technique.

Provides two attack classes:

- ``FCAttack`` — Multimodal image-based jailbreak for VLMs (paper-faithful).
- ``tFCAttack`` — Text-only graph encoding attack for any LLM.

Reference: Zhang et al., "FC-Attack: Jailbreaking Multimodal Large
Language Models via Auto-Generated Flowcharts" (EMNLP 2025 Findings)
https://arxiv.org/abs/2502.21059
"""

from .attack import FCAttack, tFCAttack

__all__ = ["FCAttack", "tFCAttack"]
