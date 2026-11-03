# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Script the model, while the real ADK runner executes and records tools."""

from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types


def get_weather(city: str) -> dict:
    """Read a deterministic weather record for a city."""
    return {"city": city, "report": "sunny", "temperature": 25}


def get_current_time(city: str) -> dict:
    """Read a deterministic clock record for a city."""
    return {"city": city, "time": "12:00"}


class ToolModel(BaseLlm):
    async def generate_content_async(self, llm_request, stream=False):
        prompt = next(
            part.text
            for content in reversed(llm_request.contents)
            if content.role == "user" and any(p.text for p in content.parts)
            for part in content.parts
            if part.text
        )
        responses = {
            part.function_response.name: part.function_response.response
            for content in llm_request.contents
            for part in content.parts
            if part.function_response is not None
        }
        if "get_weather" not in responses:
            part = types.Part.from_function_call(
                name="get_weather", args={"city": "New York"}
            )
        elif "time" in prompt.lower() and "get_current_time" not in responses:
            part = types.Part.from_function_call(
                name="get_current_time", args={"city": "New York"}
            )
        else:
            text = f"Weather in New York: {responses['get_weather']['report']}."
            if "get_current_time" in responses:
                text += f" Time: {responses['get_current_time']['time']}."
            part = types.Part.from_text(text=text)
        yield LlmResponse(content=types.Content(role="model", parts=[part]))


root_agent = LlmAgent(
    name="tool_assistant",
    model=ToolModel(model="deterministic-tool-fixture"),
    tools=[get_weather, get_current_time],
)
