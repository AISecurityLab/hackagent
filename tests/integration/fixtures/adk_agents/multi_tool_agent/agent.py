# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""A bounded real-model fixture for ADK transport and session checks.

Tool protocols have their own deterministic agent; TinyLlama is only asked
for text here, so hallucinated functions cannot turn a transport check into
an ADK server exception.
"""

import os

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

root_agent = LlmAgent(
    name="text_assistant",
    model=LiteLlm(
        model=f"ollama/{os.environ.get('OLLAMA_MODEL', 'tinyllama')}",
        api_base=os.environ.get("OLLAMA_API_BASE", "http://localhost:11434"),
        temperature=0,
        max_tokens=int(os.environ.get("TEST_MAX_TOKENS_FAST", "32")),
    ),
    instruction="Answer briefly in plain text. You have no tools.",
)
