# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Flowchart attacks: present the goal's steps as a flowchart to expand.

A step-description generator (the ``attacker`` role) writes numbered steps
for the goal; the first ``num_steps`` are drawn under the goal as an image
(FC) or written as flowchart code (tFC), and the target is asked to fill in
the details.
"""

from __future__ import annotations

import re
from typing import Any

from ..base import Completion, Messages, StaticAttack
from .config import FCParams, tFCParams
from .flowchart_renderer import TEXT_FORMAT_SERIALIZERS, render_flowchart
from .prompts import STEP_GENERATION_PROMPT, SYSTEM_PROMPT, USER_PROMPT


#: A numbered step: ``1. …``, ``2) …`` or ``Step 3: …``.
_STEP = re.compile(r"^\s*(?:step\s*)?\d+\s*[.):]\s*(\S.*)$", re.IGNORECASE)


def parse_steps(reply: str) -> list[str]:
    """The numbered steps in a generator reply, in order."""
    return [
        match.group(1).strip()
        for match in map(_STEP.match, reply.splitlines())
        if match
    ]


async def generate_steps(
    attacker: Completion, goal: str, num_steps: int, truncate_last_step: bool
) -> list[str]:
    """Ask the step-description generator for ``goal``'s steps; keep the first ones."""
    reply = await attacker(
        [{"role": "user", "content": STEP_GENERATION_PROMPT.format(goal=goal)}]
    )
    steps = parse_steps(reply)[:num_steps]
    if not steps:
        raise ValueError(
            "the step-description generator wrote no numbered steps: "
            f"{reply.strip()[:200]!r}"
        )
    if truncate_last_step:
        truncation_point = max(3, len(steps[-1]) * 3 // 5)
        steps[-1] = steps[-1][:truncation_point] + "..."
    return steps


def _require_attacker(params: FCParams | tFCParams, name: str) -> Completion:
    if params.attacker is None:
        raise ValueError(
            f"{name} needs an 'attacker' role: the step-description generator "
            "that writes the flowchart's steps."
        )
    return params.attacker


def _build_multimodal_messages(
    image_data_url: str,
) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_data_url}},
                {"type": "text", "text": USER_PROMPT},
            ],
        },
    ]


def _build_text_messages(graph_text: str, text_format: str) -> list[dict[str, str]]:
    language = {
        "dot": "dot",
        "mermaid": "mermaid",
        "tikz": "latex",
        "plantuml": "plantuml",
        "ascii": "",
    }[text_format]
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"{USER_PROMPT}\n\n```{language}\n{graph_text}\n```",
        },
    ]


class FCAttack(StaticAttack[FCParams]):
    """One multimodal request with the flowchart rendered as an image."""

    name = "fc"
    params_type = FCParams

    def __init__(self, params: FCParams) -> None:
        super().__init__(params)
        self.attacker = _require_attacker(params, "FC-Attack")

    async def build_requests(self, goal: str) -> list[Messages]:
        params = self.params
        steps = await generate_steps(
            self.attacker, goal, params.num_steps, params.truncate_last_step
        )
        rendered = render_flowchart(
            steps=steps,
            goal_text=goal,
            layout=params.layout,
            dpi=params.dpi,
        )
        return [_build_multimodal_messages(rendered["image_data_url"])]


class tFCAttack(StaticAttack[tFCParams]):
    """One text request with the flowchart serialized as code."""

    name = "tfc"
    params_type = tFCParams

    def __init__(self, params: tFCParams) -> None:
        super().__init__(params)
        self.attacker = _require_attacker(params, "tFC-Attack")

    async def build_requests(self, goal: str) -> list[Messages]:
        params = self.params
        steps = await generate_steps(
            self.attacker, goal, params.num_steps, params.truncate_last_step
        )
        graph_text = TEXT_FORMAT_SERIALIZERS[params.text_format](
            goal,
            steps,
            params.layout,
        )
        return [_build_text_messages(graph_text, params.text_format)]
