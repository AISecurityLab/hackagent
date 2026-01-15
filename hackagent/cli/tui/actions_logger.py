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
TUI Actions Logger

Custom logging handler that extracts and displays agent actions (tool calls, HTTP requests)
in the TUI actions viewer.
"""

import logging
import re
from typing import Any, Callable


class TUIActionsHandler(logging.Handler):
    """
    Custom logging handler that extracts agent actions from log messages
    and displays them in the TUI actions viewer.

    This handler parses log messages to identify:
    - HTTP requests to agent endpoints
    - Tool/function calls with arguments
    - ADK agent events (tool_call, tool_result, llm_response)
    - API responses
    """

    def __init__(
        self,
        actions_callback: Callable,
        app_callback: Callable,
        level: int = logging.INFO,
    ):
        """
        Initialize the actions handler.

        Args:
            actions_callback: Callback function to add actions to the viewer
                            Signature: (action_type: str, **kwargs)
            app_callback: Callback to call actions from thread-safe context
            level: Logging level
        """
        super().__init__(level)
        self.actions_callback = actions_callback
        self.app_callback = app_callback

    def emit(self, record: logging.LogRecord) -> None:
        """
        Process a log record and extract action information.

        Args:
            record: The log record to process
        """
        try:
            message = record.getMessage()

            # Pattern 1: HTTP requests to agent endpoints
            # Example: "🌐 Sending request to agent endpoint: http://localhost:8000/run"
            if "Sending request to agent endpoint:" in message or "🌐" in message:
                url_match = re.search(r"(https?://[^\s]+)", message)
                if url_match:
                    url = url_match.group(1)
                    method = "POST"  # Most agent requests are POST
                    self.app_callback(
                        self.actions_callback,
                        "http_request",
                        method=method,
                        url=url,
                    )

            # Pattern 2: Tool calls (from _log_agent_actions in completions.py)
            # Example: "🔧 Agent actions for prefix #1:"
            elif "🔧 Agent actions" in message or "Tool:" in message:
                # Extract tool name if present
                tool_match = re.search(r"Tool:\s*(\w+)", message)
                if tool_match:
                    tool_name = tool_match.group(1)
                    self.app_callback(
                        self.actions_callback,
                        "tool_call",
                        tool_name=tool_name,
                    )

            # Pattern 3: ADK events
            # Example: "🤖 ADK Agent actions for prefix #1:"
            elif "🤖 ADK Agent actions" in message or "ADK" in message:
                # Check subsequent messages for event details
                if "Tool Call:" in message:
                    tool_match = re.search(r"Tool Call:\s*(\w+)", message)
                    if tool_match:
                        tool_name = tool_match.group(1)
                        self.app_callback(
                            self.actions_callback,
                            "adk_event",
                            event_type="tool_call",
                            tool_name=tool_name,
                        )
                elif "Tool Result:" in message:
                    tool_match = re.search(r"Tool Result:\s*(\w+)", message)
                    if tool_match:
                        tool_name = tool_match.group(1)
                        self.app_callback(
                            self.actions_callback,
                            "adk_event",
                            event_type="tool_result",
                            tool_name=tool_name,
                        )
                elif "LLM Response:" in message:
                    content_match = re.search(r"LLM Response:\s*(.+)", message)
                    content = content_match.group(1) if content_match else ""
                    self.app_callback(
                        self.actions_callback,
                        "adk_event",
                        event_type="llm_response",
                        content=content,
                    )

            # Pattern 4: Agent responses
            # Example: "✅ Agent responded with status 200"
            elif "Agent responded" in message or "✅" in message:
                status_match = re.search(r"status\s+(\d+)", message)
                if status_match:
                    # This indicates a successful HTTP response
                    pass  # Could add response visualization here

            # Pattern 5: Model queries (LiteLLM)
            # Example: "🌐 Querying model gpt-4"
            elif "Querying model" in message:
                model_match = re.search(r"model\s+(\S+)", message)
                if model_match:
                    model_name = model_match.group(1)
                    self.app_callback(
                        self.actions_callback,
                        "llm_query",
                        model_name=model_name,
                    )

        except Exception:
            # Silently fail to avoid breaking the logging system
            pass


def extract_action_data_from_log(
    actions_viewer: Any,
    action_type: str,
    **kwargs: Any,
) -> None:
    """
    Extract and display action data in the actions viewer.

    Args:
        actions_viewer: The AgentActionsViewer widget
        action_type: Type of action (http_request, tool_call, adk_event, etc.)
        **kwargs: Action-specific parameters
    """
    try:
        if action_type == "http_request":
            actions_viewer.add_http_request(
                method=kwargs.get("method", "POST"),
                url=kwargs.get("url", ""),
                headers=kwargs.get("headers"),
                payload=kwargs.get("payload"),
            )

        elif action_type == "tool_call":
            actions_viewer.add_tool_call(
                tool_name=kwargs.get("tool_name", "unknown"),
                arguments=kwargs.get("arguments"),
                result=kwargs.get("result"),
            )

        elif action_type == "adk_event":
            event_type = kwargs.get("event_type", "unknown")
            event_data = {
                "tool_name": kwargs.get("tool_name", ""),
                "tool_input": kwargs.get("tool_input", {}),
                "result": kwargs.get("result", ""),
                "content": kwargs.get("content", ""),
            }
            actions_viewer.add_adk_event(event_type, event_data)

        elif action_type == "llm_query":
            # Display LLM query as a special kind of action
            model_name = kwargs.get("model_name", "unknown")
            actions_viewer.add_step_separator(f"LLM Query: {model_name}")

    except Exception:
        # Silently fail to avoid breaking the UI
        pass
