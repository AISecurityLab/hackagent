# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Response helpers for attack modules.

Prefer :class:`~hackagent.core.contracts.Completion` properties
(``text``, ``ok``, ``blocked``, ``guardrail_info``). These helpers keep
legacy envelope/dict and OpenAI-style objects working until every
technique calls ``LLM.complete``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from hackagent.core.contracts import Completion

logger = logging.getLogger("hackagent.attacks._lib.response")

GUARDRAIL_ADAPTER_TYPE = "guardrail"
GUARDRAIL_BLOCKED_MSG = "Blocked by guardrail"


def extract_response_content(
    response: Any,
    logger: Optional[logging.Logger] = None,
) -> Optional[str]:
    """Extract text content from a Completion or legacy LLM response."""
    if response is None:
        return None

    log = logger or globals()["logger"]

    if isinstance(response, Completion):
        return response.text or None

    # OpenAI-style object with choices attribute
    if hasattr(response, "choices") and response.choices:
        try:
            message = response.choices[0].message
            content = message.content if message else None
            return content or None
        except (AttributeError, IndexError) as e:
            log.debug(f"Failed to extract from OpenAI-style response: {e}")

    if isinstance(response, dict):
        content = response.get("generated_text") or response.get("processed_response")
        if content:
            return content
        error_msg = response.get("error_message")
        if error_msg:
            log.debug(f"Response contains error: {error_msg}")
            return None

    if isinstance(response, str):
        return response if response else None

    # Duck-typed Completion-like (e.g. FakeLLM extras)
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text or None

    return None


def is_guardrail_response(response: Any) -> bool:
    """Return True if *response* is a guardrail-blocked response."""
    if isinstance(response, Completion):
        return response.blocked
    if not isinstance(response, dict):
        return False
    return response.get("adapter_type") == GUARDRAIL_ADAPTER_TYPE


def get_guardrail_info(response: Any) -> Dict[str, Any]:
    """Extract guardrail metadata from a blocked response."""
    if isinstance(response, Completion):
        return response.guardrail_info
    if not is_guardrail_response(response):
        return {}
    if isinstance(response, dict):
        return response.get("agent_specific_data") or {}
    return {}
