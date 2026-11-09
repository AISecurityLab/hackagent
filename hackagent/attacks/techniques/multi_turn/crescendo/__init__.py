# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Crescendo: escalate one conversation instead of restarting it.

Implements Russinovich et al., "Great, Now Write an Article About That: The
Crescendo Multi-Turn LLM Jailbreak Attack" (2024, arXiv:2404.01833). See
:mod:`.attack` for the algorithm.
"""

from .attack import CrescendoAttack
from .config import CrescendoParams

__all__ = ["CrescendoAttack", "CrescendoParams"]
