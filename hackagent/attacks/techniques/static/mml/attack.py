# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""MML: hide the goal in an image together with decoding instructions.

Multi-Modal Linkage targets vision-language models. The goal is encrypted
into an image (words swapped for decoys, the text mirrored or rotated, or
Base64-encoded) and the accompanying text gives the key to decrypt it, so
neither the image nor the text carries the harmful request on its own; the
model only reconstructs it while answering. A game framing ("evil
alignment": the image is a screen in a villain's lair whose content must be
filled in) further steers the model toward complying.

Paper: Yu Wang, Xiaofei Zhou, Yichen Wang, Geyuan Zhang, et al., "Jailbreak
Large Vision-Language Models Through Multi-Modal Linkage", 2024,
[arXiv:2412.00473](https://arxiv.org/abs/2412.00473).

Algorithm (one goal), with the parameters of :class:`~.config.MMLParams`:

1. Encode the goal into a PNG image according to ``encoding_mode``
   (:func:`~.image_encoder.encode_prompt`), drawn as wrapped text of
   ``font_size`` in ``text_color`` on an ``image_width`` by ``image_height``
   canvas of ``background_color``:

   - ``word_replacement``: ``num_replacements`` words of the goal (preferring
     words longer than three letters) are swapped for decoy nouns before
     drawing, and the decoy-to-original mapping is kept as the key;
   - ``mirror``: the text is drawn and the image flipped horizontally;
   - ``rotate``: the text is drawn and the image rotated 180 degrees;
   - ``base64``: the Base64 encoding of the goal is drawn;
   - ``mixed``: word replacement, then the image is mirrored and rotated.

   Every mode also keeps the goal's words in shuffled order, as a check.
2. Pick the text prompt for ``encoding_mode`` and ``prompt_style``
   (:func:`~.prompts.get_prompt_template`): ``game`` is the villain's-lair
   framing, ``control`` a neutral "fill in the empty list" request. The
   prompt tells the model how to undo the transformation, carries the
   replacement dictionary and the shuffled word list, and asks it to
   reconstruct the title and then write detailed content for it.
3. Send one user message holding the text prompt and the image as an
   ``image_url`` data URL.

Deviations from the paper: decoy words and the word order shown are drawn
with Python's unseeded ``random`` module, so the request differs from run
to run; text that overflows the canvas is cut off rather than resized; and
success is decided by the campaign's evaluation panel rather than the
paper's judge. The target's reply is judged as returned, with no decoding.
Pillow is needed (the ``vision`` extra) and is imported only when the first
image is drawn.

Roles: none. The attack drives no helper model.

Attempts and success: one multimodal request per goal, sent once and judged
by the campaign's evaluation panel; the goal succeeds when that attempt
does. The target must accept image input.
"""

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
    """Encrypt the goal into an image and ask a vision model to decrypt and answer it.

    Implements Multi-Modal Linkage (Wang et al., 2024,
    [arXiv:2412.00473](https://arxiv.org/abs/2412.00473)): one multimodal
    request per goal, an image carrying the transformed goal and a text
    prompt carrying the key and a game framing, judged once by the
    campaign's evaluation panel. The target must accept images. The
    encoding modes and the deviations from the paper are documented in the
    module ``hackagent.attacks.techniques.static.mml.attack``.
    """

    name = "mml"
    params_type = MMLParams

    async def build_requests(self, goal: str) -> list[Messages]:
        """Return one user message holding the text prompt and the encoded image.

        Raises:
            ImportError: Pillow is not installed (the ``vision`` extra).
        """
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
