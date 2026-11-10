# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The Prompt Injection risk.

Tests whether the LLM executes attacker-supplied instructions that override or
bypass the system prompt. Exports the ``PromptInjectionType`` sub-types, the
``PromptInjection`` vulnerability, the ``PROMPT_INJECTION_PROFILE`` threat
profile and the ``PromptInjectionTemplate`` baseline prompts.
"""

from hackagent.catalog.risks.prompt_injection.types import PromptInjectionType
from hackagent.catalog.risks.prompt_injection.vulnerabilities import PromptInjection
from hackagent.catalog.risks.prompt_injection.templates import PromptInjectionTemplate
from hackagent.catalog.risks.prompt_injection.profile import PROMPT_INJECTION_PROFILE

__all__ = [
    "PromptInjectionType",
    "PromptInjection",
    "PromptInjectionTemplate",
    "PROMPT_INJECTION_PROFILE",
]
