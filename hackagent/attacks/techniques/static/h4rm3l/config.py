# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration for h4rm3l."""

from typing import Literal, Optional

from pydantic import Field

from ..base import AttackParams, Completion


class H4rm3lParams(AttackParams):
    """A decorator program and the model its LLM-assisted decorators use.

    ``program`` is a preset name from :data:`~.programs.PRESET_PROGRAMS` or
    a raw program. ``decorator`` is a role: it is needed only when the
    program contains an LLM-assisted decorator such as ``TranslateDecorator``.
    """

    program: str = Field(
        default="IdentityDecorator()",
        min_length=1,
        description=(
            "The obfuscation program applied to the goal: a preset name such as "
            "refusal_suppression, base64_refusal_suppression or translate_zulu, or "
            "a program written in the h4rm3l decorator language."
        ),
    )
    syntax_version: Literal[1, 2] = Field(
        default=2,
        description=(
            "Version of the h4rm3l program syntax the program is written in (1 or 2)."
        ),
    )
    decorator: Optional[Completion] = Field(
        default=None,
        exclude=True,
        repr=False,
        description=(
            "Optional. Model used by decorators that need an LLM, such as "
            "TranslateDecorator. Only needed when the program contains one."
        ),
    )
