# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tool-output indirect prompt injection (InjecAgent / OPI family).

Injects adversarial instructions into simulated (or live) tool observations
so a tool-using agent may follow a malicious goal after a benign user task.
"""

from __future__ import annotations

from .attack import ToolOutputIPIAttack

__all__ = ["ToolOutputIPIAttack"]
