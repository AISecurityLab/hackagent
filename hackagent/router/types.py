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

"""
SDK-specific types for HackAgent router.

These types are used internally by the SDK and are not part of the API models.
The API uses plain strings for agent_type, but the SDK provides enums for type safety.
"""

from enum import Enum


class AgentTypeEnum(str, Enum):
    """
    Enumeration of supported agent types in the HackAgent SDK.

    These values correspond to the string values used in the API's agent_type field.

    Endpoint Requirements by Type:
    - GOOGLE_ADK: Google Agent Development Kit endpoint (custom protocol)
    - LITELLM: Any LLM endpoint via LiteLLM (multi-provider support)
    - OPENAI_SDK: OpenAI-compatible endpoint (should end with /v1 base path)
    - LANGCHAIN: LangServe endpoint (typically /invoke or /stream)
    - MCP: Model Context Protocol endpoint (MCP-specific protocol)
    - A2A: Agent-to-Agent protocol endpoint (A2A-specific protocol)
    - UNKNOWN: Unknown agent type (fallback)

    Note: For OpenAI-compatible endpoints (OPENAI_SDK, LITELLM with custom endpoints),
    provide the base URL ending in /v1 (e.g., http://localhost:8000/v1).
    The OpenAI client will automatically append /chat/completions.
    """

    GOOGLE_ADK = "GOOGLE_ADK"
    LITELLM = "LITELLM"
    OPENAI_SDK = "OPENAI_SDK"
    LANGCHAIN = "LANGCHAIN"
    MCP = "MCP"
    A2A = "A2A"
    UNKNOWN = "UNKNOWN"

    def __str__(self) -> str:
        return str(self.value)
