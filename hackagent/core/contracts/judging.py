# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Goals, samples and verdicts."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from hackagent.core.contracts._base import FROZEN
from hackagent.core.contracts.messages import ToolCall


class Goal(BaseModel):
    """One goal to attack, with its position in the run."""

    model_config = FROZEN

    text: str
    index: int = Field(ge=0)
    labels: Dict[str, str] = Field(default_factory=dict)
    extra: Dict[str, Any] = Field(default_factory=dict)


class Sample(BaseModel):
    """One exchange to judge."""

    model_config = FROZEN

    goal: str
    prompt: str = ""
    response: str = ""
    tool_calls: List[ToolCall] = Field(default_factory=list)


class JudgeVote(BaseModel):
    """One judge's score for a sample, on the judge's native scale.

    ``error`` is set when the judge gave no usable answer: the call failed or
    the reply could not be parsed. That vote is an abstention. Its ``score``
    and ``success`` are ``None`` and aggregation leaves it out.
    """

    model_config = FROZEN

    judge: str
    score: Optional[float] = None
    success: Optional[bool] = None
    explanation: str = ""
    error: Optional[str] = None

    @property
    def abstained(self) -> bool:
        """True when this judge gave no usable answer."""
        return self.error is not None


#: Every verdict score is normalised onto 0..NORMALIZED_SCORE_MAX.
NORMALIZED_SCORE_MAX = 10.0


class Verdict(BaseModel):
    """The combined judgement of a sample.

    ``error`` is set when every judge abstained. The sample was then not
    judged: ``success`` is false and ``score`` is 0, but neither is a finding.
    Report it as unjudged, not as a failed attack.
    """

    model_config = FROZEN

    success: bool
    score: float = Field(ge=0.0, le=NORMALIZED_SCORE_MAX)
    votes: List[JudgeVote] = Field(default_factory=list)
    explanation: str = ""
    error: Optional[str] = None


__all__ = [
    "NORMALIZED_SCORE_MAX",
    "Goal",
    "JudgeVote",
    "Sample",
    "Verdict",
]
