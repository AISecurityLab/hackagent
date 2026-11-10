# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""FlipAttack: hide the goal by flipping it, then ask the target to unflip it.

Implements Liu et al., "FlipAttack: Jailbreak LLMs via Flipping" (2024,
arXiv:2410.02832). See :mod:`.attack` for the algorithm.
"""

from .attack import FlipAttack
from .config import FlipAttackParams

__all__ = ["FlipAttack", "FlipAttackParams"]
