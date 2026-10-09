# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Best-of-N: resend the goal until one perturbation of it gets through.

Based on: https://arxiv.org/abs/2412.03556
"""

from .attack import BoNAttack
from .augment import augment_text
from .config import BoNParams

__all__ = ["BoNAttack", "BoNParams", "augment_text"]
