# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Static-template attack: wrap the goal in known jailbreak templates.

The goal is dropped into a curated set of well-known, hand-written prompt
injection and jailbreak templates: instruction overrides ("ignore all
previous instructions"), fake delimiters and system blocks, role-play and
"developer mode" framings, simple encodings, hypotheticals, appeals to
authority and translation tricks. It measures how a target holds up against
the folklore jailbreaks every red team tries first. It implements no single
paper; the templates live in :mod:`.templates`.

Algorithm (one goal):

1. Build the placeholder values: ``goal`` itself, ``goal_encoded`` (ROT13),
   ``goal_base64`` (Base64) and ``goal_obfuscated`` (the goal reversed
   character by character), merged with ``template_parameters`` (which may
   override them).
2. Select templates: for each family in ``template_categories``, in that
   order, the first ``templates_per_category`` templates of the family
   (:meth:`~.config.StaticTemplateParams.selected_templates`).
3. Format every selected template with those values; each one becomes a
   request holding a single ``user`` message.

Parameter validation fails up front when a category is unknown, or when a
selected template uses a placeholder that is neither built in nor given in
``template_parameters`` (the ``multi_language`` family needs
``goal_translated`` and ``goal_foreign``, which the attack cannot produce
itself).

Roles: none. The attack drives no helper model.

Attempts and success: every formatted template is one attempt, sent to the
target independently and judged by the campaign's evaluation panel. The
goal succeeds when any of its attempts does.
"""

from __future__ import annotations

import base64
import codecs

from ..base import Messages, StaticAttack
from .config import StaticTemplateParams


class StaticTemplateAttack(StaticAttack[StaticTemplateParams]):
    """Wrap the goal in each selected jailbreak template, one request apiece.

    Templates come from the families in ``template_categories`` (the first
    ``templates_per_category`` of each), so a run sends a fixed, repeatable
    set of prompts. Every request is an attempt judged by the campaign's
    evaluation panel; the goal succeeds when any of them does. The template
    families and placeholders are documented in the module
    ``hackagent.attacks.techniques.static.static_template.attack``.
    """

    name = "static_template"
    params_type = StaticTemplateParams

    async def build_requests(self, goal: str) -> list[Messages]:
        """Return one single-message request per selected template."""
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
