# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""A client library for HackAgent — AI Agent Security Testing.

The package root exports the facade and public types only. Importing it does
not install a logging handler and does not import interface toolkits.
"""

from hackagent.client import HackAgent
from hackagent.core.contracts import AgentType
from hackagent.core.errors import ApiError, HackAgentError
from hackagent.core.settings import (
    DEFAULT_REMOTE_BASE_URL,
    Settings,
    Source,
    read_config_file,
    resolve_ollama_base_url,
    resolve_remote_base_url,
)

__all__ = (
    "AgentType",
    "ApiError",
    "DEFAULT_REMOTE_BASE_URL",
    "HackAgent",
    "HackAgentError",
    "Settings",
    "Source",
    "read_config_file",
    "resolve_ollama_base_url",
    "resolve_remote_base_url",
)
