# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Model and judge specifications."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from hackagent.core.contracts.enums import AgentType


class ModelSpec(BaseModel):
    """How to reach one model: the target or any role model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    identifier: str
    endpoint: Optional[str] = None
    agent_type: AgentType = AgentType.OPENAI_SDK
    api_key: Optional[str] = None
    api_key_env: Optional[str] = None
    max_tokens: Optional[int] = Field(default=None, ge=1)
    temperature: Optional[float] = Field(default=None, ge=0.0)
    top_p: Optional[float] = None
    timeout: Optional[float] = Field(default=None, gt=0)
    thinking: Optional[bool] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class JudgeSpec(ModelSpec):
    """A judge model and how to read its verdicts."""

    type: str = "harmbench"
    range: Optional[Literal["binary", "decimal"]] = None
    system_prompt: Optional[str] = None


__all__ = [
    "JudgeSpec",
    "ModelSpec",
]
