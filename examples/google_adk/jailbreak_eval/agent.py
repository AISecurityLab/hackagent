# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Bare Gemini agent for jailbreak evaluation.

A generic LLM agent with no system prompt and no tools — relies
entirely on the model's built-in safety guardrails.
Served via ``adk web`` so hackagent can reach it over HTTP.
"""

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

root_agent = LlmAgent(
    name="gemini_assistant",
    model=LiteLlm(model="openrouter/google/gemini-3.1-pro-preview"),
    description="A generic Gemini assistant with no custom instructions.",
)
