# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""PAP: restate the goal with one persuasion technique after another.

Implements Zeng et al., "How Johnny Can Persuade LLMs to Jailbreak Them"
(2024, arXiv:2401.06373). See :mod:`.attack` for the algorithm.
"""

from .attack import PAPAttack
from .config import PAPParams
from .taxonomy import ALL_TECHNIQUES, TOP_5_TECHNIQUES, resolve_techniques

__all__ = [
    "ALL_TECHNIQUES",
    "PAPAttack",
    "PAPParams",
    "TOP_5_TECHNIQUES",
    "resolve_techniques",
]
