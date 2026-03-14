# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Shared response extraction utilities for attack modules.

This module provides a unified helper for extracting text content from
LLM responses, eliminating the duplicated if/elif chains found across:

- pair/attack.py      (_query_attacker, _query_target_simple, _judge_response)
- baseline/generation.py  (execute_prompts)
- advprefix/generate.py   (_extract_generated_text — partial overlap)

All follow the same pattern: check for OpenAI-style .choices → check for
dict with generated_text/processed_response → fallback.

Usage:
    from hackagent.attacks.shared.response_utils import extract_response_content

    content = extract_response_content(response)
    if content is not None:
        # Process content
        ...
"""

import logging
from typing import Any, Optional

logger = logging.getLogger("hackagent.attacks.shared.response_utils")


def extract_response_content(
    response: Any,
    logger: Optional[logging.Logger] = None,
) -> Optional[str]:
    """
    Extract text content from an LLM response in various formats.

    Handles the following response formats:
    1. **OpenAI-style object** — ``response.choices[0].message.content``
    2. **Dictionary** — ``response["generated_text"]`` or
       ``response["processed_response"]``
    3. **String** — returned as-is
    4. **None / empty** — returns None

    Args:
        response: The raw response from an AgentRouter or LLM call.
            Can be an OpenAI ChatCompletion object, a dict from a
            custom adapter, a plain string, or None.
        logger: Optional logger for warnings. Falls back to module logger.

    Returns:
        The extracted text content, or None if extraction failed.

    Example:
        >>> # OpenAI-style response
        >>> content = extract_response_content(openai_response)
        >>> # Dict-style response
        >>> content = extract_response_content({"generated_text": "Hello!"})
        >>> # Plain string
        >>> content = extract_response_content("Hello!")
    """
    if response is None:
        return None

    log = logger or globals()["logger"]

    # Format 1: OpenAI-style object with choices attribute
    if hasattr(response, "choices") and response.choices:
        try:
            message = response.choices[0].message
            content = message.content if message else None
            return content or None
        except (AttributeError, IndexError) as e:
            log.debug(f"Failed to extract from OpenAI-style response: {e}")

    # Format 2: Dictionary with generated_text or processed_response
    if isinstance(response, dict):
        content = response.get("generated_text") or response.get("processed_response")
        if content:
            return content

        # Check for error
        error_msg = response.get("error_message")
        if error_msg:
            log.debug(f"Response contains error: {error_msg}")
            return None

    # Format 3: Plain string
    if isinstance(response, str):
        return response if response else None

    return None
