# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Baseline attack: the goal, unmodified.

The baseline is the control every other technique is measured against: it
sends the dataset goal to the target exactly as written, with no jailbreak
framing. Its success rate is how often the target complies with the plain
request, so the lift of any other attack over it is what that attack adds.
It implements no paper.

Algorithm (one goal):

1. Strip the goal (an empty goal raises ``ValueError``).
2. Build one request: a single ``user`` message whose content is the goal.

Roles: none. The attack drives no helper model.

Attempts and success: the runner sends the one request to the target and
the campaign's evaluation panel judges the reply. The goal has exactly one
attempt, and it succeeds when the panel says so.
"""

from __future__ import annotations

from ..base import Messages, StaticAttack
from .config import BaselineParams


class BaselineAttack(StaticAttack[BaselineParams]):
    """Send the goal, unmodified, as a single user message.

    One request per goal, judged by the campaign's evaluation panel. It is
    the control that measures how often the target complies without any
    jailbreak.
    """

    name = "baseline"
    params_type = BaselineParams

    async def build_requests(self, goal: str) -> list[Messages]:
        """Return one request holding ``goal`` as the only user message."""
        return [[{"role": "user", "content": goal}]]
