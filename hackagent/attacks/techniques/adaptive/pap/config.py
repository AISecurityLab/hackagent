# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration for PAP."""

from typing import ClassVar, List, Optional, Union

from pydantic import Field, field_validator

from ...contract import AttackParams, Completion
from .taxonomy import resolve_techniques


class PAPParams(AttackParams):
    """Which persuasion techniques to try, and the model that applies them.

    ``attacker`` is a role: the model that rewrites the goal with each
    technique, so PAP cannot run without it. Whether a technique succeeded
    is the evaluation panel's call, so there is no threshold here.
    """

    REQUIRED_ROLES: ClassVar[frozenset[str]] = frozenset({"attacker"})

    techniques: Union[str, List[str]] = Field(
        default="top5",
        description='``"top5"``, ``"all"``, or explicit technique names, tried in order.',
    )
    max_techniques: int = Field(
        default=0,
        ge=0,
        description="Upper bound on techniques tried per goal; 0 tries all of them.",
    )
    attacker: Optional[Completion] = Field(
        default=None,
        exclude=True,
        repr=False,
        description=(
            "Rewrites the goal once per persuasion technique (logical appeal, "
            "authority, …)."
        ),
    )

    @field_validator("techniques")
    @classmethod
    def validate_techniques(cls, value: Union[str, List[str]]) -> Union[str, List[str]]:
        resolve_techniques(value)
        return value


__all__ = ["PAPParams"]
