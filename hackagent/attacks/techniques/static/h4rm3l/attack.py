# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""h4rm3l: rewrite the goal through a composable chain of prompt decorators."""

from __future__ import annotations

import inspect

from ..base import Messages, StaticAttack
from .config import H4rm3lParams
from .decorators import compile_program
from .programs import resolve_program


class H4rm3lAttack(StaticAttack[H4rm3lParams]):
    """One request carrying the decorated goal."""

    name = "h4rm3l"
    params_type = H4rm3lParams

    def __init__(self, params: H4rm3lParams) -> None:
        super().__init__(params)
        self._decorate = compile_program(
            resolve_program(params.program),
            params.syntax_version,
            completion=params.decorator,
        )

    async def build_requests(self, goal: str) -> list[Messages]:
        result = self._decorate(goal)
        prompt = await result if inspect.isawaitable(result) else result
        if not isinstance(prompt, str):
            raise TypeError("decorator program must return a string")
        if not prompt.strip():
            raise ValueError("decorator program returned an empty prompt")
        return [[{"role": "user", "content": prompt}]]
