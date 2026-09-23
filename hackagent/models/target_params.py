# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Target generation parameters (moved out of attack configs).

Preferred runtime source remains ``HackAgent(..., target_config=...)``.
This typed model is the home for those knobs once Phase 5+ stops putting
them on :class:`~hackagent.attacks.config.AttackConfig`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from hackagent.core.defaults import DEFAULT_MAX_OUTPUT_TOKENS


class TargetParams(BaseModel):
    """Default generation parameters for the target (victim) model."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    max_tokens: int = Field(default=DEFAULT_MAX_OUTPUT_TOKENS, ge=1)
    temperature: float = Field(default=0.6, ge=0.0)
    top_p: Optional[float] = 1.0
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    seed: Optional[int] = None
    stop: Optional[List[str]] = None
    reasoning_effort: Optional[str] = None
    extra_body: Optional[Dict[str, Any]] = None
    response_format: Optional[Dict[str, Any]] = None
    logit_bias: Optional[Dict[str, int]] = None
    timeout: int = Field(default=120, ge=1)
    thinking: Optional[bool] = None


__all__ = ["TargetParams"]
