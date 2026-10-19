# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""MML: hide the goal in an image together with decoding instructions."""

from __future__ import annotations

from typing import Any

from ..base import Messages, StaticAttack
from .config import MMLParams
from .image_encoder import encode_prompt
from .prompts import get_prompt_template


def _build_text_prompt(
    encoding_mode: str,
    prompt_style: str,
    encoding_result: dict[str, Any],
) -> str:
    template = get_prompt_template(encoding_mode, prompt_style)
    values = {
        key: str(encoding_result[key])
        for key in ("scrambled_words", "replacement_dict")
        if key in encoding_result
    }
    return template.format(**values)


def _build_multimodal_messages(
    text_prompt: str,
    image_data_url: str,
) -> list[dict[str, Any]]:
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": text_prompt},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        }
    ]


class MMLAttack(StaticAttack[MMLParams]):
    """One multimodal request with the encoded goal as an image."""

    name = "mml"
    params_type = MMLParams

    async def build_requests(self, goal: str) -> list[Messages]:
        params = self.params
        encode_kwargs: dict[str, Any] = {
            "image_width": params.image_width,
            "image_height": params.image_height,
            "font_size": params.font_size,
            "background_color": params.background_color,
            "text_color": params.text_color,
        }
        if params.encoding_mode in {"word_replacement", "mixed"}:
            encode_kwargs["num_replacements"] = params.num_replacements

        encoded = encode_prompt(
            prompt=goal,
            encoding_mode=params.encoding_mode,
            **encode_kwargs,
        )
        text_prompt = _build_text_prompt(
            params.encoding_mode,
            params.prompt_style,
            encoded,
        )
        return [_build_multimodal_messages(text_prompt, encoded["image_data_url"])]
