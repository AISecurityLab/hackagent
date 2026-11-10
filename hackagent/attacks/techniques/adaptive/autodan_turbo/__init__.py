# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""AutoDAN-Turbo: a lifelong agent that learns jailbreak strategies.

Implements Liu et al., "AutoDAN-Turbo: A Lifelong Agent for Strategy
Self-Exploration to Jailbreak LLMs" (2024, arXiv:2410.05295). See
:mod:`.attack` for the algorithm.
"""

from .attack import AutoDANTurboAttack
from .config import AutoDANTurboParams

__all__ = ["AutoDANTurboAttack", "AutoDANTurboParams"]
