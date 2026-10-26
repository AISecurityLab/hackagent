# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration for h4rm3l."""

from collections.abc import Mapping
from typing import Any, Literal, Optional

from pydantic import Field

from ..base import AttackParams, Completion
from .decorators.compiler import program_code_decorators
from .programs import resolve_program


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

    @classmethod
    def cloud_parameter_issues(cls, parameters: Mapping[str, Any]) -> dict[str, str]:
        """A program that constructs a decorator running code it carries,
        such as ``TransformFxDecorator``, is refused."""
        program = parameters.get("program")
        if not isinstance(program, str):
            return {}
        names = program_code_decorators(
            resolve_program(program), parameters.get("syntax_version", 2)
        )
        if not names:
            return {}
        return {"program": f"{', '.join(sorted(names))} can't run in the cloud"}
