# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Flowchart attacks: image-based FC and text-based tFC.

FC implements Zhang et al., "FC-Attack: Jailbreaking Multimodal Large
Language Models via Auto-Generated Flowcharts" (Findings of EMNLP 2025,
arXiv:2502.21059); tFC is HackAgent's text-only variant. See :mod:`.attack`
for the algorithm.
"""

from .attack import FCAttack, tFCAttack
from .config import FCParams, tFCParams

__all__ = ["FCAttack", "FCParams", "tFCAttack", "tFCParams"]
