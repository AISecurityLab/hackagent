# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""FlipAttack: hide the goal by flipping it, then ask the target to unflip it."""

from .attack import FlipAttack
from .config import FlipAttackParams

__all__ = ["FlipAttack", "FlipAttackParams"]
