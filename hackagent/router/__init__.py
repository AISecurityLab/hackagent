# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Main router logic for dispatching requests to appropriate agents."""

from .adapters import (
    ADKAgent,
    OllamaAgent,
)  # This makes it easy to access agents via router module
from .router import AgentRouter
from .tracking import StepTracker, TrackingContext, track_operation

__all__ = [
    "AgentRouter",
    "ADKAgent",  # Exporting specific agents for convenience
    "OllamaAgent",  # Ollama agent for local LLMs
    "StepTracker",
    "TrackingContext",
    "track_operation",
]
