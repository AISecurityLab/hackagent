# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Baseline attack: the goal, unmodified."""

from __future__ import annotations

from ..base import Messages, StaticAttack
from .config import BaselineParams


class BaselineAttack(StaticAttack[BaselineParams]):
    """Send the goal as a single user message."""

    name = "baseline"
    params_type = BaselineParams

    async def build_requests(self, goal: str) -> list[Messages]:
        return [[{"role": "user", "content": goal}]]
