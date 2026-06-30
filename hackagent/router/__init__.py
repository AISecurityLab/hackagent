# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Main router logic for dispatching requests to appropriate agents."""

from .agent import (
    Agent,
    AdapterConfigurationError,
    AdapterInteractionError,
    AdapterResponseParsingError,
)
from .providers.adk import ADKAgent
from .providers.claude import ClaudeCodeAgent
from .providers.web import WebAgent
from .router import AgentRouter
from .tracking import StepTracker, TrackingContext, track_operation

__all__ = [
    "AgentRouter",
    "Agent",
    "ADKAgent",
    "ClaudeCodeAgent",
    "WebAgent",
    "AdapterConfigurationError",
    "AdapterInteractionError",
    "AdapterResponseParsingError",
    "StepTracker",
    "TrackingContext",
    "track_operation",
]
