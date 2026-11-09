# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Preloaded sequential tool attack chains in synthetic environments.

Implements a preloaded-chain version of Li et al., "STAC: When Innocent
Tools Form Dangerous Chains for LLM Agents" (2025, arXiv:2509.25624). See
:mod:`.attack` for the algorithm.
"""

from .attack import STACAttack
from .config import STACParams
from .environment import ChainStep, ToolChain

__all__ = ["STACAttack", "STACParams", "ChainStep", "ToolChain"]
