# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Backwards-compatibility re-export.

Issue #379 Phase E moved the Google ADK provider to
``hackagent/router/providers/adk.py`` — its logical home, since
``ADKAgent`` is a :class:`litellm.CustomLLM` wrapper rather than a chat
adapter. This module re-exports the public names so existing
``from hackagent.router.adapters.google_adk import ...`` imports keep
working.
"""

from hackagent.router.providers.adk import (  # noqa: F401
    ADKAgent,
    AgentConfigurationError,
    AgentInteractionError,
    ResponseParsingError,
    _extract_final_text,
    _get_adk_custom_llm_class,
    _last_user_text,
)
