# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""TAP: a tree of attacker prompts, pruned twice per round.

Based on: https://arxiv.org/abs/2312.02119
"""

from .attack import TAPAttack
from .config import TapParams

__all__ = ["TAPAttack", "TapParams"]
