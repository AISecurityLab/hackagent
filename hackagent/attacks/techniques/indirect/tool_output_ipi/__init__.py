# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tool-output indirect prompt injection: poison what a tool returns.

Based on InjecAgent: https://arxiv.org/abs/2403.02691
"""

from .attack import ToolOutputIPIAttack
from .config import ToolOutputIPIParams

__all__ = ["ToolOutputIPIAttack", "ToolOutputIPIParams"]
