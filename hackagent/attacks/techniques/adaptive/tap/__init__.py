# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""TAP: a tree of attacker prompts, pruned twice per round.

Implements Mehrotra et al., "Tree of Attacks: Jailbreaking Black-Box LLMs
Automatically" (2023, arXiv:2312.02119). See :mod:`.attack` for the
algorithm.
"""

from .attack import TAPAttack
from .config import TapParams

__all__ = ["TAPAttack", "TapParams"]
