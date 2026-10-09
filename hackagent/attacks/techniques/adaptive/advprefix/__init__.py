# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""AdvPrefix: write the opening the target will finish.

Based on: https://arxiv.org/abs/2412.10321
"""

from .attack import AdvPrefixAttack
from .config import AdvPrefixParams

__all__ = ["AdvPrefixAttack", "AdvPrefixParams"]
