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

# Lazy imports for adapters to improve startup time
# These adapters import heavy dependencies (litellm ~2s, google-adk ~0.1s)
from .base import (
    Agent,
    ChatCompletionsAgent,
    AdapterConfigurationError,
    AdapterInteractionError,
    AdapterResponseParsingError,
)


def __getattr__(name):
    """Lazy load adapter classes on first access."""
    if name == "ADKAgent":
        from .google_adk import ADKAgent

        return ADKAgent
    elif name == "LiteLLMAgent":
        from .litellm import LiteLLMAgent

        return LiteLLMAgent
    elif name == "OpenAIAgent":
        from .openai import OpenAIAgent

        return OpenAIAgent
    elif name == "OllamaAgent":
        from .ollama import OllamaAgent

        return OllamaAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ADKAgent",
    "LiteLLMAgent",
    "OpenAIAgent",
    "OllamaAgent",
    "Agent",
    "ChatCompletionsAgent",
    "AdapterConfigurationError",
    "AdapterInteractionError",
    "AdapterResponseParsingError",
]
