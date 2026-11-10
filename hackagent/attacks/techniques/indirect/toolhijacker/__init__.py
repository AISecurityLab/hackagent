# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""ToolHijacker: poison tool documents to influence retrieval and selection.

A gradient-free variant of Shi et al., "Prompt Injection Attack to Tool
Selection in LLM Agents" (2025, arXiv:2504.19793). See :mod:`.attack` for
the algorithm.
"""

from .attack import ToolHijackerAttack
from .config import ToolDocument, ToolHijackerParams

__all__ = ["ToolDocument", "ToolHijackerAttack", "ToolHijackerParams"]
