# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Static-template attack: wrap the goal in known jailbreak templates."""

from __future__ import annotations

import base64
import codecs

from ..base import Messages, StaticAttack
from .config import StaticTemplateParams


class StaticTemplateAttack(StaticAttack[StaticTemplateParams]):
    """One request per selected template."""

    name = "static_template"
    params_type = StaticTemplateParams

    async def build_requests(self, goal: str) -> list[Messages]:
        values = {
            "goal": goal,
            "goal_encoded": codecs.encode(goal, "rot_13"),
            "goal_base64": base64.b64encode(goal.encode()).decode(),
            "goal_obfuscated": goal[::-1],
            **self.params.template_parameters,
        }
        return [
            [{"role": "user", "content": template.format(**values)}]
            for template in self.params.selected_templates()
        ]
