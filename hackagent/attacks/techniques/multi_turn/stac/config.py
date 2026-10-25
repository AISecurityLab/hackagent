# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration for preloaded sequential tool attack chains."""

from typing import Optional

from pydantic import Field

from ...contract import AttackParams
from .environment import Scenario, ToolChain


class STACParams(AttackParams):
    scenario: Scenario = Field(
        default="data_export",
        description="Synthetic fixture: data_export, permission_change, or unreviewed_publish.",
    )
    chain: Optional[ToolChain] = Field(
        default=None,
        description="Inline declarative chain; overrides scenario. Replayed and validated before use.",
    )
    max_turns: int = Field(
        default=8,
        ge=1,
        le=64,
        description="Maximum user turns; each step supplies one turn, bounded by this limit.",
    )
    max_rounds_per_turn: int = Field(
        default=4,
        ge=1,
        le=32,
        description="Maximum target calls within a user turn, including tool-result continuations.",
    )
    max_tool_calls: int = Field(
        default=32,
        ge=1,
        le=256,
        description="Total tool execution budget per goal. Exhaustion stops the conversation.",
    )


__all__ = ["STACParams"]
