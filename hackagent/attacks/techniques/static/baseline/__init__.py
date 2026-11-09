# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Baseline attack: the goal, unmodified.

The control every other technique is compared with; see :mod:`.attack`.
"""

from .attack import BaselineAttack
from .config import BaselineParams

__all__ = ["BaselineAttack", "BaselineParams"]
