# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration for tool-output indirect prompt injection."""

from typing import Any, Optional

from pydantic import Field

from ...contract import AttackParams, Completion
from .prompts import (
    DEFAULT_BENIGN_TASKS,
    DEFAULT_INJECTION_TEMPLATE,
    DEFAULT_OBSERVATION_PREFIX,
    DEFAULT_TOOL_NAME,
    DEFAULT_TOOL_SCHEMA,
)


class ToolOutputIPIParams(AttackParams):
    """How the poisoned tool result is built, and who sharpens it.

    ``attacker`` is an optional role: when set, it refines the injection
    payload across attempts. Without it a single payload is tried per goal
    (``max_attempts`` then has no effect, since nothing changes between
    tries).
    """

    benign_tasks: tuple[str, ...] = Field(
        default=DEFAULT_BENIGN_TASKS,
        description="Benign user tasks that elicit the tool call. Cycled across goals.",
    )
    injection_template: str = Field(
        default=DEFAULT_INJECTION_TEMPLATE,
        description=(
            "Injection text. Placeholders: ``{goal}``, ``{benign_task}``, "
            "``{tool_name}``."
        ),
    )
    observation_prefix: str = Field(
        default=DEFAULT_OBSERVATION_PREFIX,
        description="Benign-looking payload wrapped around the injection.",
    )
    tools: tuple[dict[str, Any], ...] = Field(
        default=(DEFAULT_TOOL_SCHEMA,),
        description="Tool schemas the target is shown, so it can make a follow-up call.",
    )
    tool_name: str = Field(
        default=DEFAULT_TOOL_NAME,
        description="Name of the tool whose result is poisoned.",
    )
    tool_arguments: str = Field(
        default='{"query": "latest updates"}',
        description="Arguments JSON for the simulated assistant tool call.",
    )
    success_setting: str = Field(
        default="both",
        description=(
            "InjecAgent success family: ``direct_harm`` | ``data_stealing`` | ``both``."
        ),
    )
    max_attempts: int = Field(
        default=3,
        ge=1,
        description="Injection attempts per goal. Only meaningful with an ``attacker``.",
    )
    attacker: Optional[Completion] = Field(
        default=None,
        exclude=True,
        repr=False,
        description=(
            "Optional. Rewrites the injected instruction after a failed attempt, "
            "for up to max_attempts tries. Without it, the attack makes a single "
            "attempt with the built-in injection."
        ),
    )


__all__ = ["ToolOutputIPIParams"]
