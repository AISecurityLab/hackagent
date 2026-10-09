# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Crescendo: escalate one conversation instead of restarting it.

Based on: https://arxiv.org/abs/2404.01833
"""

from .attack import CrescendoAttack
from .config import CrescendoParams

__all__ = ["CrescendoAttack", "CrescendoParams"]
