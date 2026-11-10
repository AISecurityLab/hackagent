# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""System Prompt Leakage implementation."""

from typing import List, Optional
from hackagent.catalog.risks.base import BaseVulnerability
from hackagent.catalog.risks.system_prompt_leakage.types import (
    SystemPromptLeakageType,
    SYSTEM_PROMPT_LEAKAGE_TYPES,
)


class SystemPromptLeakage(BaseVulnerability):
    """The System Prompt Leakage vulnerability, with the sub-types to test.

    Args:
        types: Sub-type values to select, e.g. ``"secrets_and_credentials"``. All
            sub-types when omitted or empty.

    Raises:
        ValueError: When a value is not a ``SystemPromptLeakageType``.
    """

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
