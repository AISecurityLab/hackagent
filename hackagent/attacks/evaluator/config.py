# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration models shared by response evaluators."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator

from hackagent.attacks.techniques.config import DEFAULT_TIMEOUT


class EvaluatorConfig(BaseModel):
    """
    Configuration class for response evaluators using AgentRouter framework.
    """

    agent_name: str
    agent_type: Any  # AgentTypeEnum from hackagent.router.types
    model_id: str
    agent_endpoint: Optional[str] = None
    organization_id: Optional[int] = None
    agent_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    batch_size: int = 1
    judge_concurrency: int = 10
    max_tokens_eval: int = 512
    filter_len: int = 500
    timeout: int = DEFAULT_TIMEOUT
    temperature: float = 0.0
    max_judge_retries: int = 1
    # Optional user-defined system prompt prepended to every judge request.
    system_prompt: Optional[str] = None
    # Reasoning control passed on every judge request. Missing/None is
    # normalized to False by BaseJudgeEvaluator.
    thinking: Optional[bool] = False

    @model_validator(mode="before")
    @classmethod
    def coerce_agent_type(cls, values: Any) -> Any:
        """Coerce agent_type strings to AgentTypeEnum on construction."""
        if isinstance(values, dict) and isinstance(values.get("agent_type"), str):
            from hackagent.router.types import AgentTypeEnum

            values["agent_type"] = AgentTypeEnum(values["agent_type"])
        return values
