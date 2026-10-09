# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Flowchart attacks: present the goal as an incomplete flowchart to finish."""

from __future__ import annotations

import re
from typing import Any

from ..base import Messages, StaticAttack
from .config import FCParams, tFCParams
from .flowchart_renderer import TEXT_FORMAT_SERIALIZERS, render_flowchart
from .prompts import SYSTEM_PROMPT, USER_PROMPT


def _decompose_goal_to_steps(goal: str, num_steps: int) -> list[str]:
    sentences = [
        sentence.strip()
        for sentence in re.split(r"[.;]\s*", goal.strip())
        if sentence.strip()
    ]
    if len(sentences) >= num_steps:
        return sentences[:num_steps]

    words = goal.split()
    if len(words) <= 3:
        return [
            f"Understand the task: {goal}",
            f"Research methods for: {goal}",
            "Gather required materials",
            "Execute the plan step by step",
            f"Verify completion of: {goal}",
        ][:num_steps]

    chunk_size = max(1, len(words) // num_steps)
    steps = [
        " ".join(
            words[index * chunk_size :]
            if index == num_steps - 1
            else words[index * chunk_size : (index + 1) * chunk_size]
        )
        for index in range(num_steps)
    ]
    steps = [step for step in steps if step]
    steps.extend(
        "Continue with remaining details..." for _ in range(num_steps - len(steps))
    )
    return steps[:num_steps]


def _steps(goal: str, num_steps: int, truncate_last_step: bool) -> list[str]:
    steps = _decompose_goal_to_steps(goal, num_steps)
    if truncate_last_step and steps:
        truncation_point = max(3, len(steps[-1]) * 3 // 5)
        steps[-1] = steps[-1][:truncation_point] + "..."
    return steps


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

    async def build_requests(self, goal: str) -> list[Messages]:
        params = self.params
        rendered = render_flowchart(
            steps=_steps(goal, params.num_steps, params.truncate_last_step),
            goal_text=goal,
            layout=params.layout,
            dpi=params.dpi,
        )
        return [_build_multimodal_messages(rendered["image_data_url"])]


class tFCAttack(StaticAttack[tFCParams]):
    """One text request with the flowchart serialized as code."""

    name = "tfc"
    params_type = tFCParams

    async def build_requests(self, goal: str) -> list[Messages]:
        params = self.params
        steps = _steps(goal, params.num_steps, params.truncate_last_step)
        graph_text = TEXT_FORMAT_SERIALIZERS[params.text_format](
            goal,
            steps,
            params.layout,
        )
        return [_build_text_messages(graph_text, params.text_format)]
