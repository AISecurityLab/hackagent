# Copyright 2025 - AI4I. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
