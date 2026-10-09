# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Model and judge specifications."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    capabilities: frozenset[str] = Field(default_factory=frozenset)
    extra: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("capabilities", mode="before")
    @classmethod
    def normalize_capabilities(cls, value: Any) -> frozenset[str]:
        if value is None:
            return frozenset()
        values = [value] if isinstance(value, str) else value
        return frozenset(
            str(item).strip().lower() for item in values if str(item).strip()
        )


class JudgeSpec(ModelSpec):
    """A judge model and how to read its verdicts."""

    type: str = "harmbench"
    range: Optional[Literal["binary", "decimal"]] = None
    system_prompt: Optional[str] = None


__all__ = [
    "JudgeSpec",
    "ModelSpec",
]
