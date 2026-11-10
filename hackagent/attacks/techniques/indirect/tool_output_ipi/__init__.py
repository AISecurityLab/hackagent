# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tool-output indirect prompt injection: poison what a tool returns.

Follows Zhan et al., "InjecAgent: Benchmarking Indirect Prompt Injections
in Tool-Integrated Large Language Model Agents" (2024, arXiv:2403.02691).
See :mod:`.attack` for the algorithm.
"""

from .attack import ToolOutputIPIAttack
from .config import ToolOutputIPIParams

__all__ = ["ToolOutputIPIAttack", "ToolOutputIPIParams"]
