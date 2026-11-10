# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""AdvPrefix: write the opening the target will finish.

Implements the prefix selection of Zhu et al., "AdvPrefix: An Objective for
Nuanced LLM Jailbreaks" (2024, arXiv:2412.10321). See :mod:`.attack` for
the algorithm.
"""

from .attack import AdvPrefixAttack
from .config import AdvPrefixParams

__all__ = ["AdvPrefixAttack", "AdvPrefixParams"]
