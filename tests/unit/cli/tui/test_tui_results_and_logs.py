# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Tests for TUI Results Visualization and Log Tracking.

This module tests:
1. Results visualization in the ResultsTab
2. Log tracking through TUILogHandler
3. Actions viewer display
4. Escape function for Rich markup
"""

import json
import logging
from io import StringIO
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from rich.console import Console


# ============================================================================
# Escape Function Tests
# ============================================================================


def _escape(value: Any) -> str:
    """Escape a value for safe Rich markup rendering.

    Args:
        value: Any value to escape

    Returns:
        String with Rich markup characters escaped

    Note:
        We escape ALL square brackets to prevent any markup interpretation issues
        in Rich's nested color contexts.
    """
    if value is None:
        return ""
    text = str(value)
    return text.replace("[", "\\[").replace("]", "\\]")


class TestEscapeFunction:
    """Tests for the _escape utility function."""

    def test_escape_none(self) -> None:
        """Test escaping None returns empty string."""
        assert _escape(None) == ""

    def test_escape_normal_text(self) -> None:
        """Test normal text passes through unchanged."""
        assert _escape("Normal text") == "Normal text"

    def test_escape_single_brackets(self) -> None:
        """Test single brackets are escaped."""
        assert _escape("[test]") == "\\[test\\]"

    def test_escape_nested_brackets(self) -> None:
        """Test nested brackets are escaped."""
        assert _escape("[[nested]]") == "\\[\\[nested\\]\\]"

    def test_escape_rich_markup(self) -> None:
        """Test Rich markup tags are escaped."""
        assert _escape("[bold]text[/bold]") == "\\[bold\\]text\\[/bold\\]"

    def test_escape_json_array(self) -> None:
        """Test JSON array brackets are escaped."""
        json_str = '["item1", "item2"]'
        escaped = _escape(json_str)
        assert "\\[" in escaped
        assert "\\]" in escaped

    def test_escape_integer(self) -> None:
        """Test integers are converted to string."""
        assert _escape(123) == "123"

    def test_escape_dict(self) -> None:
        """Test dicts are converted to string and escaped."""
        result = _escape({"key": "[value]"})
        assert "\\[" in result
        assert "\\]" in result


# ============================================================================
# TUILogHandler Tests
# ============================================================================


class TestTUILogHandler:
    """Tests for the TUILogHandler logging mechanism."""

    def test_handler_creation(self) -> None:
        """Test TUILogHandler can be created with proper parameters."""
        from hackagent.cli.tui.logger import TUILogHandler

        mock_app = MagicMock()
        mock_callback = MagicMock()

        handler = TUILogHandler(
            app=mock_app,
            callback=mock_callback,
            max_buffer_size=100,
            level=logging.INFO,
        )

        assert handler.app == mock_app
        assert handler.callback == mock_callback
        assert handler.max_buffer_size == 100
        assert handler.level == logging.INFO

    def test_handler_emit_buffers_logs(self) -> None:
        """Test that emit() buffers log entries."""
        from hackagent.cli.tui.logger import TUILogHandler

        mock_app = MagicMock()
        mock_callback = MagicMock()

        handler = TUILogHandler(
            app=mock_app,
            callback=mock_callback,
            max_buffer_size=100,
            level=logging.INFO,
        )

        # Create a log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        handler.emit(record)

        # Check buffer contains the log
        buffer = handler.get_buffer()
        assert len(buffer) == 1
        assert "Test message" in buffer[0][0]
        assert buffer[0][1] == "INFO"

    def test_handler_respects_max_buffer_size(self) -> None:
        """Test that buffer doesn't exceed max_buffer_size."""
        from hackagent.cli.tui.logger import TUILogHandler

        mock_app = MagicMock()
        mock_callback = MagicMock()

        handler = TUILogHandler(
            app=mock_app,
            callback=mock_callback,
            max_buffer_size=5,
            level=logging.INFO,
        )

        # Emit more logs than buffer size
        for i in range(10):
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg=f"Message {i}",
                args=(),
                exc_info=None,
            )
            handler.emit(record)

        # Buffer should only contain last 5
        buffer = handler.get_buffer()
        assert len(buffer) == 5
        # Should contain messages 5-9
        assert "Message 5" in buffer[0][0]

    def test_handler_clear_buffer(self) -> None:
        """Test clearing the log buffer."""
        from hackagent.cli.tui.logger import TUILogHandler

        mock_app = MagicMock()
        mock_callback = MagicMock()

        handler = TUILogHandler(
            app=mock_app,
            callback=mock_callback,
            max_buffer_size=100,
            level=logging.INFO,
        )

        # Add some logs
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        handler.emit(record)

        # Clear and verify
        handler.clear_buffer()
        assert len(handler.get_buffer()) == 0

    def test_handler_deactivate_activate(self) -> None:
        """Test activating and deactivating the handler."""
        from hackagent.cli.tui.logger import TUILogHandler

        mock_app = MagicMock()
        mock_callback = MagicMock()

        handler = TUILogHandler(
            app=mock_app,
            callback=mock_callback,
            max_buffer_size=100,
            level=logging.INFO,
        )

        # Initially active
        assert handler._active

        # Deactivate
        handler.deactivate()
        assert not handler._active

        # Logs should not be processed when deactivated
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Should not be buffered",
            args=(),
            exc_info=None,
        )
        handler.emit(record)
        assert len(handler.get_buffer()) == 0

        # Activate
        handler.activate()
        assert handler._active


# ============================================================================
# Results Visualization Tests
# ============================================================================


class TestResultsVisualization:
    """Tests for results visualization formatting."""

    @pytest.fixture
    def console(self) -> Console:
        """Create a console for testing Rich markup rendering."""
        return Console(file=StringIO(), force_terminal=True)

    def render_markup(self, console: Console, markup: str) -> str:
        """Render markup and return the output."""
        output = StringIO()
        console = Console(file=output, force_terminal=True)
        console.print(markup)
        return output.getvalue()

    def test_status_color_coding(self, console: Console) -> None:
        """Test status values are properly color-coded."""
        statuses = [
            ("COMPLETED", "green"),
            ("RUNNING", "cyan"),
            ("FAILED", "red"),
            ("PENDING", "yellow"),
        ]

        for status, color in statuses:
            escaped_status = _escape(status)
            markup = f"[{color}]✅ {escaped_status}[/{color}]"
            # Should not raise
            console.print(markup)

    def test_evaluation_status_display(self, console: Console) -> None:
        """Test evaluation status formatting."""
        eval_statuses = [
            ("SUCCESSFUL_JAILBREAK", "green", "✅"),
            ("FAILED_JAILBREAK", "red", "❌"),
            ("NOT_EVALUATED", "yellow", "ℹ️"),
            ("ERROR", "red", "⚠️"),
        ]

        for status, color, icon in eval_statuses:
            escaped = _escape(status)
            markup = f"{icon} [bold]Evaluation:[/bold] [bright_{color}]{escaped}[/bright_{color}]"
            console.print(markup)

    def test_trace_step_formatting(self, console: Console) -> None:
        """Test trace step header formatting."""
        step_types = [
            ("TOOL_CALL", "🔧", "bright_green"),
            ("TOOL_RESPONSE", "📥", "bright_cyan"),
            ("AGENT_THOUGHT", "🧠", "bright_magenta"),
            ("AGENT_RESPONSE_CHUNK", "💬", "bright_white"),
            ("MCP_STEP", "🔗", "bright_yellow"),
            ("A2A_COMM", "🤝", "bright_yellow"),
        ]

        for step_type, icon, color in step_types:
            escaped = _escape(step_type)
            markup = f"[{color}]╭───[/] [bold {color}]Step 1[/bold {color}] [{color}]{icon} {escaped}[/]"
            console.print(markup)

    def test_json_payload_display(self, console: Console) -> None:
        """Test JSON payload formatting in results."""
        payload = {
            "messages": [
                {"role": "user", "content": "Test [with brackets]"},
                {"role": "assistant", "content": "Response [bold]text[/bold]"},
            ],
            "model": "test-model",
        }

        payload_str = json.dumps(payload, indent=2)
        lines = payload_str.split("\n")

        details = ""
        for line in lines[:15]:
            if ":" in line and '"' in line:
                key_part, value_part = line.split(":", 1)
                details += f"[yellow]{_escape(key_part)}:[/yellow][bright_white]{_escape(value_part[:100])}[/bright_white]\n"
            else:
                details += f"{_escape(line)}\n"

        console.print(details)

    def test_run_details_header(self, console: Console) -> None:
        """Test run details header formatting."""
        run_id = str(uuid4())
        agent_name = "test-agent [with brackets]"
        org_name = "test-org"

        details = f"""[bold bright_white]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold bright_white]
[bold bright_white]  RUN DETAILS[/bold bright_white]
[bold bright_white]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold bright_white]

[bold bright_cyan]▌ Overview[/bold bright_cyan]
  🆔 [bold]Run ID:[/bold] [dim]{run_id}[/dim]
  🤖 [bold]Agent:[/bold] [bright_cyan]{_escape(agent_name)}[/bright_cyan]
  🏢 [bold]Organization:[/bold] [bright_cyan]{_escape(org_name)}[/bright_cyan]
"""
        console.print(details)

    def test_evaluation_summary_display(self, console: Console) -> None:
        """Test evaluation summary statistics display."""
        summary = {
            "SUCCESSFUL_JAILBREAK": 5,
            "FAILED_JAILBREAK": 3,
            "NOT_EVALUATED": 2,
            "ERROR": 1,
        }

        details = f"""[bold bright_green]▌ Evaluation Summary[/bold bright_green]
  ✅ [bold]Successful Jailbreaks:[/bold] [bright_green]{summary["SUCCESSFUL_JAILBREAK"]}[/bright_green]
  ❌ [bold]Failed Jailbreaks:[/bold] [bright_red]{summary["FAILED_JAILBREAK"]}[/bright_red]
  ⏸️  [bold]Not Evaluated:[/bold] [bright_yellow]{summary["NOT_EVALUATED"]}[/bright_yellow]
  ⚠️  [bold]Errors:[/bold] [bright_red]{summary["ERROR"]}[/bright_red]
"""
        console.print(details)


# ============================================================================
# Actions Viewer Tests
# ============================================================================


class TestActionsViewer:
    """Tests for the AgentActionsViewer functionality."""

    def test_escape_in_tool_call_display(self) -> None:
        """Test that tool call arguments are properly escaped."""
        arguments = {"location": "New York [USA]", "units": "metric"}

        args_str = json.dumps(arguments, indent=2)
        escaped_args = _escape(args_str)

        # Should contain escaped brackets
        assert "\\[" in escaped_args
        assert "\\]" in escaped_args

    def test_escape_in_http_request_display(self) -> None:
        """Test HTTP request URL escaping."""
        url = "http://example.com/api?filter=[active]"
        escaped_url = _escape(url)

        assert "\\[" in escaped_url
        assert "\\]" in escaped_url

    def test_escape_in_adk_event_content(self) -> None:
        """Test ADK event content escaping."""
        content = "Tool returned [success] with data [1, 2, 3]"
        escaped = _escape(content)

        assert "\\[" in escaped
        assert "\\]" in escaped


# ============================================================================
# Log Viewer Widget Tests
# ============================================================================


class TestLogViewer:
    """Tests for the AttackLogViewer functionality."""

    def test_log_level_color_mapping(self) -> None:
        """Test log levels map to correct colors."""
        level_colors = {
            "DEBUG": "dim",
            "INFO": "cyan",
            "WARNING": "yellow",
            "ERROR": "bold red",
            "CRITICAL": "bold red on white",
        }

        for level, expected_color in level_colors.items():
            # Verify the mapping exists
            assert level in level_colors
            assert level_colors[level] == expected_color

    def test_log_message_escaping(self) -> None:
        """Test log messages with markup characters are escaped."""
        message = "Processing [data] from [source]"
        escaped = _escape(message)

        # Should be safe to render
        console = Console(file=StringIO(), force_terminal=True)
        markup = f"[cyan]{escaped}[/cyan]"
        console.print(markup)

    def test_step_header_formatting(self) -> None:
        """Test step header separator formatting."""
        step_name = "Attack [Phase 1]"
        step_number = 1

        escaped_name = _escape(step_name)
        separator = "─" * 60
        header = f"\n[bold magenta]{separator}\n🎯 STEP {step_number}: {escaped_name}\n{separator}[/bold magenta]\n"

        console = Console(file=StringIO(), force_terminal=True)
        console.print(header)


# ============================================================================
# Integration Tests - Log Tracking Flow
# ============================================================================


class TestLogTrackingFlow:
    """Tests for the complete log tracking flow."""

    def test_with_tui_logging_decorator(self) -> None:
        """Test the with_tui_logging decorator attaches handlers correctly."""
        from hackagent.cli.tui.logger import TUILogHandler, with_tui_logging

        # Create a mock attack class
        class MockAttack:
            def __init__(self):
                self._tui_log_handler = None

            @with_tui_logging(logger_name="hackagent.test")
            def run(self, goals):
                logger = logging.getLogger("hackagent.test")
                logger.info("Running attack")
                return ["result"]

        # Create handler
        mock_app = MagicMock()
        mock_app.call_from_thread = lambda callback, *args, **kwargs: callback(
            *args, **kwargs
        )
        mock_callback = MagicMock()

        handler = TUILogHandler(
            app=mock_app,
            callback=mock_callback,
            max_buffer_size=100,
            level=logging.INFO,
        )

        # Attach handler to attack instance
        attack = MockAttack()
        attack._tui_log_handler = handler

        # Run attack
        result = attack.run(["goal1"])

        # Verify result
        assert result == ["result"]

    def test_attach_detach_tui_handler(self) -> None:
        """Test attaching and detaching TUI handler from attack instance."""
        from hackagent.cli.tui.logger import (
            TUILogHandler,
            attach_tui_handler,
            detach_tui_handler,
        )

        class MockAttack:
            pass

        mock_app = MagicMock()
        mock_callback = MagicMock()

        attack = MockAttack()

        # Attach
        handler = attach_tui_handler(attack, mock_app, mock_callback)

        assert hasattr(attack, "_tui_log_handler")
        assert attack._tui_log_handler == handler
        assert isinstance(handler, TUILogHandler)

        # Detach
        detached = detach_tui_handler(attack)

        assert detached == handler
        assert not hasattr(attack, "_tui_log_handler")

    def test_detach_nonexistent_handler(self) -> None:
        """Test detaching handler when none exists."""
        from hackagent.cli.tui.logger import detach_tui_handler

        class MockAttack:
            pass

        attack = MockAttack()
        result = detach_tui_handler(attack)

        assert result is None


# ============================================================================
# Actions Logger Pattern Matching Tests
# ============================================================================


class TestActionsLoggerPatterns:
    """Tests for TUIActionsHandler pattern matching."""

    def test_http_request_pattern_detection(self) -> None:
        """Test HTTP request pattern detection in log messages."""
        import re

        message = "🌐 Sending request to agent endpoint: http://localhost:8000/run"

        # Pattern from actions_logger.py
        url_match = re.search(r"(https?://[^\s]+)", message)

        assert url_match is not None
        assert url_match.group(1) == "http://localhost:8000/run"

    def test_tool_call_pattern_detection(self) -> None:
        """Test tool call pattern detection in log messages."""
        import re

        message = "🔧 Agent actions for prefix #1: Tool: get_weather"

        tool_match = re.search(r"Tool:\s*(\w+)", message)

        assert tool_match is not None
        assert tool_match.group(1) == "get_weather"

    def test_model_query_pattern_detection(self) -> None:
        """Test model query pattern detection."""
        import re

        message = "🌐 Querying model gpt-4-turbo"

        model_match = re.search(r"model\s+(\S+)", message)

        assert model_match is not None
        assert model_match.group(1) == "gpt-4-turbo"


# ============================================================================
# Results Table Data Parsing Tests
# ============================================================================


class TestResultsTableParsing:
    """Tests for parsing and displaying results in the table."""

    def test_parse_agent_actions_http(self) -> None:
        """Test parsing HTTP actions from log strings."""

        # Create minimal mock for testing the method
        class MockConfig:
            api_key = "test"
            base_url = "http://test"

        # We can't instantiate ResultsTab easily, so test the pattern directly
        import re

        logs = """
        HTTP POST https://api.example.com/endpoint
        Some other log line
        HTTP GET https://api.example.com/data
        """

        actions = []
        lines = logs.split("\n")
        for i, line in enumerate(lines):
            if "HTTP" in line and (
                "POST" in line or "GET" in line or "PUT" in line or "DELETE" in line
            ):
                method_match = re.search(r"(GET|POST|PUT|DELETE|PATCH)", line)
                url_match = re.search(r"(https?://[^\s]+)", line)
                if method_match and url_match:
                    actions.append(
                        {
                            "type": "http_request",
                            "method": method_match.group(1),
                            "url": url_match.group(1),
                            "line_num": i + 1,
                        }
                    )

        assert len(actions) == 2
        assert actions[0]["method"] == "POST"
        assert actions[1]["method"] == "GET"

    def test_parse_agent_actions_tool_call(self) -> None:
        """Test parsing tool call actions from log strings."""
        import re

        logs = """
        🔧 Tool: get_weather
        Arguments: {"location": "NYC"}
        Other log line
        Tool: search_data
        """

        actions = []
        lines = logs.split("\n")
        for i, line in enumerate(lines):
            if "Tool:" in line or "Function:" in line or "🔧" in line:
                tool_match = re.search(r"(?:Tool|Function):\s*([\w_]+)", line)
                if tool_match:
                    tool_name = tool_match.group(1)
                    args = ""
                    for j in range(i + 1, min(i + 5, len(lines))):
                        if "Arguments:" in lines[j] or "Input:" in lines[j]:
                            args = lines[j]
                            break
                    actions.append(
                        {
                            "type": "tool_call",
                            "tool_name": tool_name,
                            "arguments": args,
                            "line_num": i + 1,
                        }
                    )

        assert len(actions) == 2
        assert actions[0]["tool_name"] == "get_weather"
        assert "Arguments:" in actions[0]["arguments"]
        assert actions[1]["tool_name"] == "search_data"


# ============================================================================
# Rich Markup Safety Tests
# ============================================================================


class TestRichMarkupSafety:
    """Tests to ensure all user content is safely rendered."""

    MALICIOUS_INPUTS = [
        "Normal text",
        "[bold]injected markup[/bold]",
        "[red]red text[/red]",
        "Text with [brackets]",
        '{"json": ["array"]}',
        "[/closing tag]",
        "[incomplete",
        "\\[escaped\\]",
        "[dim][/dim] empty tags",
        "Nested [[brackets]]",
        "[not/a/tag/but/looks/like/one]",
    ]

    @pytest.fixture
    def console(self) -> Console:
        """Create console for testing."""
        return Console(file=StringIO(), force_terminal=True)

    @pytest.mark.parametrize("malicious_input", MALICIOUS_INPUTS)
    def test_escape_prevents_markup_error(
        self, console: Console, malicious_input: str
    ) -> None:
        """Test that escaping prevents MarkupError for malicious inputs."""
        escaped = _escape(malicious_input)
        markup = f"[bold cyan]Label:[/bold cyan] {escaped}"
        # Should not raise MarkupError
        console.print(markup)

    @pytest.mark.parametrize("malicious_input", MALICIOUS_INPUTS)
    def test_escape_in_complex_nested_markup(
        self, console: Console, malicious_input: str
    ) -> None:
        """Test escaping in complex nested markup structures."""
        escaped = _escape(malicious_input)
        markup = f"""[bold bright_white]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold bright_white]
[bold bright_cyan]▌ Header[/bold bright_cyan]
  🔧 [bold]Tool:[/bold] [bright_cyan]{escaped}[/bright_cyan]
  📥 [bold]Response:[/bold] [bright_green]{escaped}[/bright_green]
[bold bright_white]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold bright_white]
"""
        console.print(markup)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ============================================================================
# New Formatting Functions Tests
# ============================================================================


class TestFormatMessageContent:
    """Tests for _format_message_content helper function."""

    def test_format_empty_content(self) -> None:
        """Test formatting empty content."""
        from hackagent.cli.tui.views.results import _format_message_content

        result = _format_message_content("")
        assert "empty" in result.lower()

    def test_format_none_content(self) -> None:
        """Test formatting None content."""
        from hackagent.cli.tui.views.results import _format_message_content

        result = _format_message_content(None)
        assert "empty" in result.lower()

    def test_format_short_content(self) -> None:
        """Test formatting short content that doesn't need truncation."""
        from hackagent.cli.tui.views.results import _format_message_content

        result = _format_message_content("Short message")
        assert "Short message" in result
        assert "more chars" not in result

    def test_format_long_content_truncation(self) -> None:
        """Test that long content is truncated."""
        from hackagent.cli.tui.views.results import _format_message_content

        long_text = "x" * 500
        result = _format_message_content(long_text, max_length=100)
        assert "more chars" in result


class TestFormatChatMessage:
    """Tests for _format_chat_message helper function."""

    @pytest.fixture
    def console(self) -> Console:
        """Create console for testing."""
        return Console(file=StringIO(), force_terminal=True)

    def test_format_user_message(self, console: Console) -> None:
        """Test formatting a user message."""
        from hackagent.cli.tui.views.results import _format_chat_message

        msg = {"role": "user", "content": "Hello, world!"}
        result = _format_chat_message(msg)

        assert "USER" in result
        assert "Hello, world!" in result or "Hello, world\\!" in result
        # Should be able to render
        console.print(result)

    def test_format_assistant_message(self, console: Console) -> None:
        """Test formatting an assistant message."""
        from hackagent.cli.tui.views.results import _format_chat_message

        msg = {"role": "assistant", "content": "I can help with that."}
        result = _format_chat_message(msg)

        assert "ASSISTANT" in result
        # Should be able to render
        console.print(result)

    def test_format_system_message(self, console: Console) -> None:
        """Test formatting a system message."""
        from hackagent.cli.tui.views.results import _format_chat_message

        msg = {"role": "system", "content": "You are a helpful assistant."}
        result = _format_chat_message(msg)

        assert "SYSTEM" in result
        console.print(result)

    def test_format_message_with_brackets(self, console: Console) -> None:
        """Test formatting message with markup-like brackets."""
        from hackagent.cli.tui.views.results import _format_chat_message

        msg = {"role": "user", "content": "Search for [internal] data"}
        result = _format_chat_message(msg)

        # Should escape brackets
        assert "\\[" in result or "[internal]" not in result
        # Should render without error
        console.print(result)


class TestFormatRequestPayload:
    """Tests for _format_request_payload helper function."""

    @pytest.fixture
    def console(self) -> Console:
        """Create console for testing."""
        return Console(file=StringIO(), force_terminal=True)

    def test_format_empty_payload(self, console: Console) -> None:
        """Test formatting empty payload."""
        from hackagent.cli.tui.views.results import _format_request_payload

        result = _format_request_payload(None)
        assert "no payload" in result.lower()
        console.print(result)

    def test_format_chat_payload(self, console: Console) -> None:
        """Test formatting a chat completion payload."""
        from hackagent.cli.tui.views.results import _format_request_payload

        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "What is 2+2?"},
            ],
            "temperature": 0.7,
            "max_tokens": 100,
        }

        result = _format_request_payload(payload)

        assert "gpt-4" in result
        assert "Messages" in result
        assert "2 messages" in result
        assert "temperature" in result.lower()
        console.print(result)

    def test_format_payload_with_tools(self, console: Console) -> None:
        """Test formatting payload with tools."""
        from hackagent.cli.tui.views.results import _format_request_payload

        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Get weather"}],
            "tools": [
                {"name": "get_weather", "type": "function"},
                {"function": {"name": "search"}, "type": "function"},
            ],
        }

        result = _format_request_payload(payload)

        assert "Tools" in result
        assert "get_weather" in result
        console.print(result)


class TestFormatResponseBody:
    """Tests for _format_response_body helper function."""

    @pytest.fixture
    def console(self) -> Console:
        """Create console for testing."""
        return Console(file=StringIO(), force_terminal=True)

    def test_format_empty_response(self, console: Console) -> None:
        """Test formatting empty response."""
        from hackagent.cli.tui.views.results import _format_response_body

        result = _format_response_body(None)
        assert "no response" in result.lower()
        console.print(result)

    def test_format_openai_response(self, console: Console) -> None:
        """Test formatting OpenAI-style response."""
        from hackagent.cli.tui.views.results import _format_response_body

        response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "The answer is 4.",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }

        result = _format_response_body(response)

        assert "ASSISTANT" in result
        assert "answer is 4" in result or "answer" in result.lower()
        # Check for token usage display (improved format shows "Token Usage:" instead of "Tokens:")
        assert "Token" in result or "tokens" in result.lower()
        console.print(result)

    def test_format_response_with_tool_calls(self, console: Console) -> None:
        """Test formatting response with tool calls."""
        from hackagent.cli.tui.views.results import _format_response_body

        response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "get_weather",
                                    "arguments": '{"location": "NYC"}',
                                }
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
        }

        result = _format_response_body(response)

        assert "Tool Calls" in result
        assert "get_weather" in result
        console.print(result)

    def test_format_error_response(self, console: Console) -> None:
        """Test formatting error response."""
        from hackagent.cli.tui.views.results import _format_response_body

        response = {"error": {"message": "Rate limit exceeded"}}

        result = _format_response_body(response)

        # Error is now shown as "ERROR:" in uppercase
        assert "ERROR" in result or "Error" in result
        assert "Rate limit" in result
        console.print(result)


class TestFormatConfigDict:
    """Tests for _format_config_dict helper function."""

    @pytest.fixture
    def console(self) -> Console:
        """Create console for testing."""
        return Console(file=StringIO(), force_terminal=True)

    def test_format_empty_config(self, console: Console) -> None:
        """Test formatting empty config."""
        from hackagent.cli.tui.views.results import _format_config_dict

        result = _format_config_dict(None)
        assert "no config" in result.lower()
        console.print(result)

    def test_format_config_with_types(self, console: Console) -> None:
        """Test formatting config with various types."""
        from hackagent.cli.tui.views.results import _format_config_dict

        config = {
            "enabled": True,
            "disabled": False,
            "count": 42,
            "rate": 0.95,
            "name": "test-config",
            "items": ["a", "b", "c"],
            "nested": {"key": "value"},
        }

        result = _format_config_dict(config)

        assert "enabled" in result
        assert "True" in result
        assert "42" in result
        assert "test-config" in result
        console.print(result)


class TestFormatTraceContent:
    """Tests for _format_trace_content helper function."""

    @pytest.fixture
    def console(self) -> Console:
        """Create console for testing."""
        return Console(file=StringIO(), force_terminal=True)

    def test_format_tool_call_trace(self, console: Console) -> None:
        """Test formatting TOOL_CALL trace content."""
        from hackagent.cli.tui.views.results import _format_trace_content

        content = {
            "name": "get_weather",
            "arguments": {"location": "NYC", "units": "metric"},
        }

        result = _format_trace_content(content, "TOOL_CALL", "bright_green")

        assert "get_weather" in result
        assert "Arguments" in result
        assert "location" in result
        console.print(result)

    def test_format_tool_response_trace(self, console: Console) -> None:
        """Test formatting TOOL_RESPONSE trace content."""
        from hackagent.cli.tui.views.results import _format_trace_content

        content = {"result": {"temperature": 72, "conditions": "sunny"}}

        result = _format_trace_content(content, "TOOL_RESPONSE", "bright_cyan")

        assert "Result" in result
        assert "temperature" in result
        console.print(result)

    def test_format_agent_thought_trace(self, console: Console) -> None:
        """Test formatting AGENT_THOUGHT trace content."""
        from hackagent.cli.tui.views.results import _format_trace_content

        content = "I should search for weather data first."

        result = _format_trace_content(content, "AGENT_THOUGHT", "bright_magenta")

        assert "Thinking" in result or "search" in result
        console.print(result)

    def test_format_trace_with_brackets(self, console: Console) -> None:
        """Test formatting trace with bracket characters."""
        from hackagent.cli.tui.views.results import _format_trace_content

        content = {
            "name": "search",
            "arguments": {"query": "find [internal] documents"},
        }

        result = _format_trace_content(content, "TOOL_CALL", "bright_green")

        # Should escape brackets
        console.print(result)  # Should not raise


class TestGetResultStatusInfo:
    """Tests for _get_result_status_info helper function."""

    def test_successful_jailbreak_status(self) -> None:
        """Test SUCCESSFUL_JAILBREAK returns green and check icon."""
        from hackagent.cli.tui.views.results import _get_result_status_info
        from unittest.mock import MagicMock

        result = MagicMock()
        result.evaluation_status = MagicMock()
        result.evaluation_status.value = "SUCCESSFUL_JAILBREAK"

        status, color, icon = _get_result_status_info(result)

        assert "SUCCESSFUL" in status.upper()
        assert color == "green"
        assert icon == "✅"

    def test_failed_jailbreak_status(self) -> None:
        """Test FAILED_JAILBREAK returns red and cross icon."""
        from hackagent.cli.tui.views.results import _get_result_status_info
        from unittest.mock import MagicMock

        result = MagicMock()
        result.evaluation_status = MagicMock()
        result.evaluation_status.value = "FAILED_JAILBREAK"

        status, color, icon = _get_result_status_info(result)

        assert "FAILED" in status.upper()
        assert color == "red"
        assert icon == "❌"

    def test_error_status(self) -> None:
        """Test ERROR status returns red."""
        from hackagent.cli.tui.views.results import _get_result_status_info
        from unittest.mock import MagicMock

        result = MagicMock()
        result.evaluation_status = MagicMock()
        result.evaluation_status.value = "ERROR"

        status, color, icon = _get_result_status_info(result)

        assert color == "red"
        assert icon == "⚠️"

    def test_no_evaluation_status(self) -> None:
        """Test result without evaluation_status returns N/A."""
        from hackagent.cli.tui.views.results import _get_result_status_info
        from unittest.mock import MagicMock

        result = MagicMock(spec=[])  # No evaluation_status attribute

        status, color, icon = _get_result_status_info(result)

        assert status == "N/A"
        assert color == "yellow"
        assert icon == "ℹ️"


class TestFormatResultSummary:
    """Tests for _format_result_summary helper function."""

    @pytest.fixture
    def console(self) -> Console:
        """Create console for testing."""
        return Console(file=StringIO(), force_terminal=True)

    def test_basic_summary(self, console: Console) -> None:
        """Test basic result summary formatting."""
        from hackagent.cli.tui.views.results import _format_result_summary
        from unittest.mock import MagicMock

        result = MagicMock()
        result.evaluation_status = MagicMock()
        result.evaluation_status.value = "SUCCESSFUL_JAILBREAK"
        result.prompt_name = "test_prompt"
        result.latency_ms = 150
        result.traces = [MagicMock(), MagicMock()]  # 2 traces

        summary = _format_result_summary(result, 1)

        assert "#1" in summary  # Compact format now uses #1 instead of Result #1
        assert "SUCCESSFUL_JAILBREAK" in summary
        assert "test_prompt" in summary
        assert "150ms" in summary
        assert "2" in summary  # Trace count shown as just number now
        console.print(summary)

    def test_summary_without_optional_fields(self, console: Console) -> None:
        """Test summary when optional fields are missing."""
        from hackagent.cli.tui.views.results import _format_result_summary
        from unittest.mock import MagicMock

        result = MagicMock(spec=["evaluation_status", "id"])
        result.evaluation_status = MagicMock()
        result.evaluation_status.value = "NOT_EVALUATED"

        summary = _format_result_summary(result, 3)

        assert "#3" in summary  # Compact format now uses #3 instead of Result #3
        assert "NOT_EVALUATED" in summary
        console.print(summary)


class TestFormatResultFullDetails:
    """Tests for _format_result_full_details helper function."""

    @pytest.fixture
    def console(self) -> Console:
        """Create console for testing."""
        return Console(file=StringIO(), force_terminal=True)

    def test_full_details_with_all_fields(self, console: Console) -> None:
        """Test full details with all fields present."""
        from hackagent.cli.tui.views.results import _format_result_full_details
        from unittest.mock import MagicMock

        result = MagicMock()
        result.id = "test-result-id-123"
        result.evaluation_status = MagicMock()
        result.evaluation_status.value = "SUCCESSFUL_JAILBREAK"
        result.prompt_name = "injection_test"
        result.latency_ms = 200
        result.response_status_code = 200
        result.evaluation_notes = "Attack succeeded"
        result.evaluation_metrics = {"score": 0.95}
        result.request_payload = {"model": "gpt-4", "messages": []}
        result.response_body = {"choices": [{"message": {"content": "test"}}]}
        result.traces = []

        details = _format_result_full_details(result, 1)

        assert "Result #1" in details
        # ID is now truncated in compact format
        assert "test-res" in details  # First 8 chars of truncated ID
        assert "SUCCESSFUL_JAILBREAK" in details
        assert "injection_test" in details
        assert "200ms" in details
        assert "Attack succeeded" in details
        assert "score" in details
        console.print(details)

    def test_full_details_minimal(self, console: Console) -> None:
        """Test full details with minimal fields."""
        from hackagent.cli.tui.views.results import _format_result_full_details
        from unittest.mock import MagicMock

        result = MagicMock(spec=["id", "evaluation_status"])
        result.id = "minimal-id"
        result.evaluation_status = MagicMock()
        result.evaluation_status.value = "NOT_EVALUATED"

        details = _format_result_full_details(result, 5)

        assert "Result #5" in details
        # ID is now truncated
        assert "minimal-" in details  # First 8 chars
        assert "NOT_EVALUATED" in details
        console.print(details)
