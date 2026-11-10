# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The System Prompt Leakage risk.

Tests whether the LLM reveals sensitive details from its system prompt, such as
credentials, internal instructions, or guardrails. Exports the
``SystemPromptLeakageType`` sub-types, the ``SystemPromptLeakage``
vulnerability and the ``SYSTEM_PROMPT_LEAKAGE_PROFILE`` threat profile.
"""

from hackagent.catalog.risks.system_prompt_leakage.types import SystemPromptLeakageType
from hackagent.catalog.risks.system_prompt_leakage.vulnerabilities import (
    SystemPromptLeakage,
)
from hackagent.catalog.risks.system_prompt_leakage.profile import (
    SYSTEM_PROMPT_LEAKAGE_PROFILE,
)

__all__ = [
    "SystemPromptLeakageType",
    "SystemPromptLeakage",
    "SYSTEM_PROMPT_LEAKAGE_PROFILE",
]
