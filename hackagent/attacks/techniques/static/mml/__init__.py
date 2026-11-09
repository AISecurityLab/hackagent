# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""MML: hide the goal in an image together with decoding instructions.

Implements Wang et al., "Jailbreak Large Vision-Language Models Through
Multi-Modal Linkage" (2024, arXiv:2412.00473). See :mod:`.attack` for the
algorithm.
"""

from .attack import MMLAttack
from .config import MMLParams

__all__ = ["MMLAttack", "MMLParams"]
