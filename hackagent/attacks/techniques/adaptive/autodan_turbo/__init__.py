# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""AutoDAN-Turbo: a lifelong agent that learns jailbreak strategies.

Based on: https://arxiv.org/abs/2410.05295
"""

from .attack import AutoDANTurboAttack
from .config import AutoDANTurboParams

__all__ = ["AutoDANTurboAttack", "AutoDANTurboParams"]
