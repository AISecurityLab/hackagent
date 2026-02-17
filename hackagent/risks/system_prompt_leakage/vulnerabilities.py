# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""System Prompt Leakage implementation."""

from typing import List, Optional
from hackagent.risks.base import BaseVulnerability
from hackagent.risks.system_prompt_leakage.types import (
    SystemPromptLeakageType,
    SYSTEM_PROMPT_LEAKAGE_TYPES,
)


class SystemPromptLeakage(BaseVulnerability):
    """System Prompt Leakage."""

    name = "System Prompt Leakage"
    description = (
        "Tests whether the LLM reveals sensitive details from its system prompt, "
        "such as credentials, internal instructions, or guardrails."
    )
    ALLOWED_TYPES = [t.value for t in SystemPromptLeakageType]
    _type_enum = SystemPromptLeakageType

    def __init__(self, types: Optional[List[str]] = None):
        if types:
            resolved = [SystemPromptLeakageType(t) for t in types]
        else:
            resolved = list(SYSTEM_PROMPT_LEAKAGE_TYPES)
        super().__init__(types=resolved)
