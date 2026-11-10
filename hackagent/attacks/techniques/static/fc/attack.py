# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Flowchart attacks: present the goal's steps as a flowchart to expand.

FC-Attack moves the harmful content out of the text channel: a helper model
writes short, generic steps for the goal, the steps are drawn as a
flowchart under the goal, and the target is asked, under a "win the
million-dollar quiz" persona, to analyse the flowchart and complete every
step in detail. Vision-language models tend to treat the image as a
legitimate task to elaborate rather than a request to refuse. tFC is
HackAgent's text-only variant: the same flowchart is written as diagram
source code (Graphviz DOT, Mermaid, TikZ, PlantUML or ASCII art), so the
technique also reaches models without image input.

Paper: Ziyi Zhang, Zhen Sun, Zongmin Zhang, Jihui Guo, et al., "FC-Attack:
Jailbreaking Multimodal Large Language Models via Auto-Generated
Flowcharts", Findings of EMNLP 2025,
[arXiv:2502.21059](https://arxiv.org/abs/2502.21059). The step prompt and
the target prompts follow the authors' code,
https://github.com/ZZYHKUSTGZ/FC_Attack.

Algorithm (one goal), with the parameters of :class:`~.config.FCParams` and
:class:`~.config.tFCParams`:

1. Ask the ``attacker`` role (the step-description generator) for the
   goal's steps with the authors' few-shot prompt
   (:data:`~.prompts.STEP_GENERATION_PROMPT`), and parse the numbered lines
   of its reply (:func:`parse_steps`). A reply with no numbered step fails
   the goal.
2. Keep the first ``num_steps`` steps. With ``truncate_last_step`` the last
   one is cut to about three fifths of its length and ends in ``...``.
3. FC: draw the goal as the first node and the steps below it with Graphviz
   in the chosen ``layout`` (``vertical``, ``horizontal``, or
   ``tortuous``/``s_shaped``, a snake of three-node rows) at ``dpi``, and
   send the PNG as an image after the system prompt, with the instruction
   to analyse and complete the flowchart
   (:func:`~.flowchart_renderer.render_flowchart`).
   tFC: serialize the same flowchart as ``text_format`` source in that
   ``layout`` and send it in a fenced code block after the same
   instruction.

Deviations from the paper: the authors' generator is Mistral-7B-Instruct
fine-tuned on benign how-to steps, whose weights are not released, so any
chat model that answers in the numbered format stands in as ``attacker``;
the few-shot prompt takes the goal as the instruction where the authors
used a topic. ``truncate_last_step`` and the whole tFC variant are
HackAgent additions. Success is decided by the campaign's evaluation panel
rather than the paper's judge.

Roles: ``attacker`` (required), the step-description generator, called once
per goal; its call is traced on the goal's first attempt.

Attempts and success: one request per goal, sent once and judged by the
campaign's evaluation panel; the goal succeeds when that attempt does. FC
needs a target that accepts images and a Graphviz ``dot`` binary, found on
``PATH``, through ``HACKAGENT_GRAPHVIZ_DOT``, or downloaded on first use
unless ``HACKAGENT_GRAPHVIZ_AUTO_DOWNLOAD=0``.
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
    """Ask the step-description generator for ``goal``'s steps; keep the first ones.

    Calls ``attacker`` once. Returns at most ``num_steps`` steps; with
    ``truncate_last_step`` the last is cut to about three fifths of its
    length and ends in ``...``.

    Raises:
        ValueError: The reply holds no numbered step.
    """
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
    """Draw helper-written steps for the goal as a flowchart image and ask for the details.

    Implements FC-Attack (Zhang et al., Findings of EMNLP 2025,
    [arXiv:2502.21059](https://arxiv.org/abs/2502.21059)): the ``attacker``
    role writes the goal's steps, Graphviz draws them under the goal, and
    one multimodal request asks the target to complete the flowchart. That
    one attempt is judged by the campaign's evaluation panel. The target
    must accept images. The step-by-step algorithm and the deviations from
    the paper are documented in the module
    ``hackagent.attacks.techniques.static.fc.attack``.
    """

    name = "fc"
    params_type = FCParams

    def __init__(self, params: FCParams) -> None:
        super().__init__(params)
        self.attacker = _require_attacker(params, "FC-Attack")

    async def build_requests(self, goal: str) -> list[Messages]:
        """Generate the steps, render the flowchart, and return the one multimodal request.

        Calls the ``attacker`` role once.

        Raises:
            ValueError: The generator's reply holds no numbered step.
            RuntimeError: No Graphviz ``dot`` binary could be found or installed.
        """
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
    """Write helper-written steps for the goal as flowchart source code and ask for the details.

    HackAgent's text-only variant of FC-Attack (Zhang et al., Findings of
    EMNLP 2025, [arXiv:2502.21059](https://arxiv.org/abs/2502.21059)): the
    ``attacker`` role writes the goal's steps, they are serialized as DOT,
    Mermaid, TikZ, PlantUML or ASCII art, and one text request asks the
    target to complete the flowchart. That one attempt is judged by the
    campaign's evaluation panel. The step-by-step algorithm is documented
    in the module ``hackagent.attacks.techniques.static.fc.attack``.
    """

    name = "tfc"
    params_type = tFCParams

    def __init__(self, params: tFCParams) -> None:
        super().__init__(params)
        self.attacker = _require_attacker(params, "tFC-Attack")

    async def build_requests(self, goal: str) -> list[Messages]:
        """Generate the steps, serialize the flowchart, and return the one text request.

        Calls the ``attacker`` role once.

        Raises:
            ValueError: The generator's reply holds no numbered step.
        """
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
