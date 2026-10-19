# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""PAP: restate the goal with one persuasion technique after another.

Based on: https://arxiv.org/abs/2401.06373
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
