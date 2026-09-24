# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Shared vocabulary: the values that cross package boundaries.

Every package may import this package. It holds data definitions and
protocols only, no behaviour beyond validation and small properties.
Import from here; the topic modules are an implementation detail:

- :mod:`~hackagent.core.contracts.enums`: ``AgentType``, ``RunStatus``,
  ``StepKind``, ``EvalStatus``
- :mod:`~hackagent.core.contracts.messages`: ``ToolCall``, ``Message``
- :mod:`~hackagent.core.contracts.completion`: ``Usage``, ``RawExchange``,
  ``LLMError``, ``GuardrailInfo``, ``Completion``
- :mod:`~hackagent.core.contracts.specs`: ``ModelSpec``, ``JudgeSpec``
- :mod:`~hackagent.core.contracts.judging`: ``Goal``, ``Sample``,
  ``JudgeVote``, ``Verdict``, ``NORMALIZED_SCORE_MAX``
- :mod:`~hackagent.core.contracts.protocols`: ``LLM``, ``LLMFactory``
"""

from hackagent.core.contracts.completion import (
    Completion,
    GuardrailInfo,
    LLMError,
    RawExchange,
    Usage,
)
from hackagent.core.contracts.enums import AgentType, EvalStatus, RunStatus, StepKind
from hackagent.core.contracts.judging import (
    NORMALIZED_SCORE_MAX,
    Goal,
    JudgeVote,
    Sample,
    Verdict,
)
from hackagent.core.contracts.messages import Message, ToolCall
from hackagent.core.contracts.protocols import LLM, LLMFactory
from hackagent.core.contracts.specs import JudgeSpec, ModelSpec

__all__ = [
    "AgentType",
    "Completion",
    "EvalStatus",
    "Goal",
    "GuardrailInfo",
    "JudgeSpec",
    "JudgeVote",
    "LLM",
    "LLMError",
    "LLMFactory",
    "Message",
    "ModelSpec",
    "NORMALIZED_SCORE_MAX",
    "RawExchange",
    "RunStatus",
    "Sample",
    "StepKind",
    "ToolCall",
    "Usage",
    "Verdict",
]
