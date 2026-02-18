# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Prompt Injection implementation."""

from typing import List, Optional
from hackagent.risks.base import BaseVulnerability
from hackagent.risks.prompt_injection.types import (
    PromptInjectionType,
    PROMPT_INJECTION_TYPES,
)


class PromptInjection(BaseVulnerability):
    """Prompt Injection."""

    name = "Prompt Injection"
    description = (
        "Tests whether the LLM executes attacker-supplied instructions "
        "that override or bypass the system prompt."
    )
    ALLOWED_TYPES = [t.value for t in PromptInjectionType]
    _type_enum = PromptInjectionType

    def __init__(self, types: Optional[List[str]] = None):
        if types:
            resolved = [PromptInjectionType(t) for t in types]
        else:
            resolved = list(PROMPT_INJECTION_TYPES)
        super().__init__(types=resolved)
