# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Prompt Injection sub-types."""

from enum import Enum


class PromptInjectionType(Enum):
    """Sub-types for Prompt Injection."""

    DIRECT_INJECTION = "direct_injection"
    """User prompt directly overrides system instructions."""
    INDIRECT_INJECTION = "indirect_injection"
    """Malicious instructions are embedded in retrieved/external content."""

    CONTEXT_MANIPULATION = "context_manipulation"
    """Crafted context tricks the model into ignoring guardrails."""


PROMPT_INJECTION_TYPES = list(PromptInjectionType)
