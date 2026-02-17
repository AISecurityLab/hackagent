# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Results Tab

View and analyze attack results.
"""

from datetime import datetime
import datetime as dt_module
from dateutil import tz
import json
from typing import Any
from uuid import UUID

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Collapsible, DataTable, Label, Select, Static

from hackagent.cli.config import CLIConfig


def _escape(value: Any) -> str:
    """Escape a value for safe Rich markup rendering.

    Args:
        value: Any value to escape

    Returns:
        String with Rich markup characters escaped

    Note:
        We escape ALL square brackets, not just tag-like patterns,
        because Rich's markup parser can get confused by unescaped
        brackets in certain contexts (e.g., JSON arrays inside colored text).
    """
    if value is None:
        return ""
    # Escape ALL square brackets to prevent any markup interpretation issues
    # Rich's escape() only escapes tag-like patterns, but single brackets
    # can still cause issues in nested color contexts
    text = str(value)
    return text.replace("[", "\\[").replace("]", "\\]")


def _format_message_content(content: str, max_length: int = 300) -> str:
    """Format a message content string for display.

    Args:
        content: The message content
        max_length: Maximum length before truncation

    Returns:
        Formatted and escaped string
    """
    if not content:
        return "[dim]<empty>[/dim]"

    # Truncate if needed
    display_content = content[:max_length]
    truncated = len(content) > max_length

    # Escape for safe rendering
    escaped = _escape(display_content)

    if truncated:
        escaped += f" [dim]... ({len(content) - max_length} more chars)[/dim]"

    return escaped


def _format_chat_message(message: dict, indent: str = "     ") -> str:
    """Format a chat message (role + content) for readable display.

    Args:
        message: Dict with 'role' and 'content' keys
        indent: Indentation prefix

    Returns:
        Formatted message string
    """
    role = message.get("role", "unknown")
    content = message.get("content", "")

    # Role colors and icons
    role_styles = {
        "system": ("bright_yellow", "⚙️"),
        "user": ("bright_cyan", "👤"),
        "assistant": ("bright_green", "🤖"),
        "tool": ("bright_magenta", "🔧"),
        "function": ("bright_magenta", "📞"),
    }

    color, icon = role_styles.get(role.lower(), ("white", "💬"))

    output = f"{indent}[{color}]{icon} {role.upper()}[/{color}]\n"

    # Handle content based on type
    if isinstance(content, str):
        # Split long content into readable lines
        content_lines = content.split("\n")
        for i, line in enumerate(content_lines[:10]):  # Limit lines
            if line.strip():
                output += f"{indent}  [dim]│[/dim] {_escape(line[:200])}\n"
        if len(content_lines) > 10:
            output += (
                f"{indent}  [dim]│ ... ({len(content_lines) - 10} more lines)[/dim]\n"
            )
    elif isinstance(content, list):
        # Multi-part content (e.g., with images)
        for part in content[:5]:
            if isinstance(part, dict):
                part_type = part.get("type", "unknown")
                if part_type == "text":
                    text = part.get("text", "")[:200]
                    output += f"{indent}  [dim]│[/dim] {_escape(text)}\n"
                elif part_type == "image_url":
                    output += f"{indent}  [dim]│[/dim] [bright_yellow]📷 <image>[/bright_yellow]\n"
                else:
                    output += f"{indent}  [dim]│[/dim] [{part_type}]\n"
    else:
        output += f"{indent}  [dim]│[/dim] {_escape(str(content)[:200])}\n"

    return output


def _format_request_payload(payload: Any, indent: str = "     ") -> str:
    """Format a request payload for human-readable display.

    Args:
        payload: The request payload (dict or string)
        indent: Indentation prefix

    Returns:
        Formatted string for display
    """
    if not payload:
        return f"{indent}[dim]<no payload>[/dim]\n"

    output = ""

    try:
        # Parse if string
        if isinstance(payload, str):
            payload = json.loads(payload)

        if not isinstance(payload, dict):
            return f"{indent}{_escape(str(payload)[:500])}\n"

        # Extract and display key fields intelligently
        # Model
        if "model" in payload:
            output += f"{indent}[bold]Model:[/bold] [bright_cyan]{_escape(payload['model'])}[/bright_cyan]\n"

        # Messages (chat format)
        if "messages" in payload and isinstance(payload["messages"], list):
            output += f"{indent}[bold]Messages:[/bold] ({len(payload['messages'])} messages)\n"
            for i, msg in enumerate(payload["messages"][:5]):  # Show first 5 messages
                if isinstance(msg, dict):
                    output += _format_chat_message(msg, indent)
            if len(payload["messages"]) > 5:
                output += f"{indent}[dim]... {len(payload['messages']) - 5} more messages[/dim]\n"

        # Prompt (completion format)
        elif "prompt" in payload:
            prompt = payload["prompt"]
            output += f"{indent}[bold]Prompt:[/bold]\n"
            if isinstance(prompt, str):
                lines = prompt.split("\n")[:10]
                for line in lines:
                    output += f"{indent}  [dim]│[/dim] {_escape(line[:200])}\n"
                if len(prompt.split("\n")) > 10:
                    output += f"{indent}  [dim]│ ... (more lines)[/dim]\n"
            else:
                output += f"{indent}  {_escape(str(prompt)[:300])}\n"

        # Temperature, max_tokens, etc.
        params_shown = []
        for param in ["temperature", "max_tokens", "top_p", "top_k", "n"]:
            if param in payload:
                params_shown.append(f"{param}={payload[param]}")
        if params_shown:
            output += f"{indent}[bold]Parameters:[/bold] [dim]{', '.join(params_shown)}[/dim]\n"

        # Tools if present
        if "tools" in payload and payload["tools"]:
            tool_names = []
            for tool in payload["tools"][:10]:
                if isinstance(tool, dict):
                    name = tool.get("name") or tool.get("function", {}).get("name", "?")
                    tool_names.append(name)
            if tool_names:
                output += f"{indent}[bold]Tools:[/bold] [bright_magenta]{_escape(', '.join(tool_names))}[/bright_magenta]\n"
            if len(payload["tools"]) > 10:
                output += (
                    f"{indent}[dim]... {len(payload['tools']) - 10} more tools[/dim]\n"
                )

        # If we didn't extract anything meaningful, show summary
        if not output:
            keys = list(payload.keys())[:10]
            output += f"{indent}[dim]Keys: {_escape(', '.join(keys))}[/dim]\n"

    except (json.JSONDecodeError, TypeError, AttributeError):
        # Fallback to raw display
        output = f"{indent}{_escape(str(payload)[:500])}\n"

    return output


def _format_response_body(response: Any, indent: str = "     ") -> str:
    """Format a response body for human-readable display.

    Handles various response formats including:
    - OpenAI Chat Completions (choices with messages)
    - OpenAI Completions (choices with text)
    - Anthropic Claude responses
    - Generic JSON responses
    - Error responses

    Args:
        response: The response body (dict, string, or other)
        indent: Indentation prefix

    Returns:
        Formatted string for display
    """
    if not response:
        return f"{indent}[dim]<no response>[/dim]\n"

    output = ""

    try:
        # Parse if string
        if isinstance(response, str):
            try:
                response = json.loads(response)
            except json.JSONDecodeError:
                # Plain text response
                output += f"{indent}[bright_white]📝 Text Response:[/bright_white]\n"
                lines = response.split("\n")[:20]
                for line in lines:
                    if line.strip():
                        output += f"{indent}  [dim]│[/dim] {_escape(line[:200])}\n"
                if len(response.split("\n")) > 20:
                    output += f"{indent}  [dim]│ ... (more lines)[/dim]\n"
                return output

        if not isinstance(response, dict):
            return f"{indent}{_escape(str(response)[:500])}\n"

        # --- Model Information ---
        model = response.get("model")
        if model:
            output += f"{indent}[bold]🤖 Model:[/bold] [bright_cyan]{_escape(model)}[/bright_cyan]\n"

        # --- Response ID ---
        response_id = response.get("id")
        if response_id:
            output += f"{indent}[bold]🆔 Response ID:[/bold] [dim]{_escape(response_id)}[/dim]\n"

        # --- OpenAI Chat Completions Format (choices with messages) ---
        if "choices" in response and isinstance(response["choices"], list):
            for i, choice in enumerate(response["choices"][:3]):
                if isinstance(choice, dict):
                    # Index info if multiple choices
                    if len(response["choices"]) > 1:
                        output += f"\n{indent}[bold bright_yellow]Choice {i + 1}:[/bold bright_yellow]\n"

                    # Get message object
                    msg = choice.get("message", {})
                    if msg:
                        role = msg.get("role", "assistant")
                        content = msg.get("content")

                        # Role indicator
                        role_icon = "🤖" if role == "assistant" else "📥"
                        role_color = (
                            "bright_green" if role == "assistant" else "bright_cyan"
                        )
                        output += f"{indent}[{role_color}]{role_icon} {_escape(role.upper())} RESPONSE[/{role_color}]\n"

                        # Content
                        if content:
                            content_lines = content.split("\n")[:20]
                            for line in content_lines:
                                if line.strip():
                                    output += f"{indent}  [dim]│[/dim] {_escape(line[:200])}\n"
                            if len(content.split("\n")) > 20:
                                output += f"{indent}  [dim]│ ... ({len(content.split(chr(10))) - 20} more lines)[/dim]\n"
                        elif content == "":
                            output += f"{indent}  [dim]│ (empty content - likely tool call)[/dim]\n"

                        # Refusal (OpenAI safety)
                        refusal = msg.get("refusal")
                        if refusal:
                            output += f"{indent}  [bold red]🚫 Refusal:[/bold red] {_escape(refusal)}\n"

                        # Tool calls
                        tool_calls = msg.get("tool_calls", [])
                        if tool_calls:
                            output += f"\n{indent}  [bright_magenta]🔧 Tool Calls ({len(tool_calls)}):[/bright_magenta]\n"
                            for j, tc in enumerate(tool_calls[:5], 1):
                                if isinstance(tc, dict):
                                    tc_id = tc.get("id", "")
                                    func = tc.get("function", {})
                                    tc_name = func.get("name", "unknown")
                                    tc_args = func.get("arguments", "{}")

                                    output += f"{indent}    [{j}] [bright_cyan]{_escape(tc_name)}[/bright_cyan]"
                                    if tc_id:
                                        output += (
                                            f" [dim]({_escape(tc_id[:20])}...)[/dim]"
                                        )
                                    output += "\n"

                                    # Parse and format arguments
                                    try:
                                        args_dict = (
                                            json.loads(tc_args)
                                            if isinstance(tc_args, str)
                                            else tc_args
                                        )
                                        if isinstance(args_dict, dict):
                                            for k, v in list(args_dict.items())[:5]:
                                                v_str = str(v)[:100]
                                                output += f"{indent}        {_escape(k)}: [yellow]{_escape(v_str)}[/yellow]\n"
                                            if len(args_dict) > 5:
                                                output += f"{indent}        [dim]... ({len(args_dict) - 5} more args)[/dim]\n"
                                    except Exception:
                                        output += f"{indent}        {_escape(str(tc_args)[:150])}\n"

                            if len(tool_calls) > 5:
                                output += f"{indent}    [dim]... ({len(tool_calls) - 5} more tool calls)[/dim]\n"

                    # Text completion format (legacy)
                    text = choice.get("text", "")
                    if text and not msg:
                        output += (
                            f"{indent}[bright_green]📝 COMPLETION[/bright_green]\n"
                        )
                        lines = text.split("\n")[:15]
                        for line in lines:
                            if line.strip():
                                output += f"{indent}  {_escape(line[:200])}\n"
                        if len(text.split("\n")) > 15:
                            output += f"{indent}  [dim]... (more lines)[/dim]\n"

                    # Finish reason
                    finish = choice.get("finish_reason")
                    if finish:
                        finish_icon = (
                            "✅"
                            if finish == "stop"
                            else "🔧"
                            if finish == "tool_calls"
                            else "📏"
                            if finish == "length"
                            else "⚠️"
                        )
                        finish_color = (
                            "green"
                            if finish == "stop"
                            else "magenta"
                            if finish == "tool_calls"
                            else "yellow"
                        )
                        output += f"{indent}  [{finish_color}]{finish_icon} Finish Reason: {_escape(finish)}[/{finish_color}]\n"

                    # Log probabilities (if present)
                    logprobs = choice.get("logprobs")
                    if logprobs:
                        output += f"{indent}  [dim]📊 Logprobs available[/dim]\n"

        # --- Anthropic Claude Format ---
        if "content" in response and isinstance(response["content"], list):
            output += f"{indent}[bright_green]🤖 CLAUDE RESPONSE[/bright_green]\n"
            for block in response["content"][:5]:
                if isinstance(block, dict):
                    block_type = block.get("type", "text")
                    if block_type == "text":
                        text = block.get("text", "")
                        if text:
                            lines = text.split("\n")[:15]
                            for line in lines:
                                if line.strip():
                                    output += f"{indent}  [dim]│[/dim] {_escape(line[:200])}\n"
                    elif block_type == "tool_use":
                        tool_name = block.get("name", "unknown")
                        tool_input = block.get("input", {})
                        output += f"{indent}  [bright_magenta]🔧 Tool Use:[/bright_magenta] [bright_cyan]{_escape(tool_name)}[/bright_cyan]\n"
                        if isinstance(tool_input, dict):
                            for k, v in list(tool_input.items())[:3]:
                                output += f"{indent}      {_escape(k)}: [yellow]{_escape(str(v)[:80])}[/yellow]\n"

            # Claude stop reason
            stop_reason = response.get("stop_reason")
            if stop_reason:
                output += f"{indent}  [dim]Stop Reason: {_escape(stop_reason)}[/dim]\n"

        # --- Usage Statistics ---
        usage = response.get("usage", {})
        if isinstance(usage, dict) and usage:
            output += f"\n{indent}[bold]📊 Token Usage:[/bold]\n"
            prompt_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
            completion_tokens = usage.get(
                "completion_tokens", usage.get("output_tokens")
            )
            total_tokens = usage.get("total_tokens")

            if prompt_tokens is not None:
                output += f"{indent}  • Input:  [cyan]{prompt_tokens:,}[/cyan] tokens\n"
            if completion_tokens is not None:
                output += (
                    f"{indent}  • Output: [cyan]{completion_tokens:,}[/cyan] tokens\n"
                )
            if total_tokens is not None:
                output += f"{indent}  • Total:  [bright_cyan]{total_tokens:,}[/bright_cyan] tokens\n"

            # Cached tokens (OpenAI)
            cached = usage.get("prompt_tokens_details", {}).get("cached_tokens")
            if cached:
                output += f"{indent}  • Cached: [dim]{cached:,}[/dim] tokens\n"

        # --- Error Handling ---
        if "error" in response:
            err = response["error"]
            output += f"\n{indent}[bold red]⚠️ ERROR:[/bold red]\n"
            if isinstance(err, dict):
                err_type = err.get("type", "unknown")
                err_msg = err.get("message", str(err))
                err_code = err.get("code")
                output += f"{indent}  Type: [red]{_escape(err_type)}[/red]\n"
                if err_code:
                    output += f"{indent}  Code: [red]{_escape(str(err_code))}[/red]\n"
                output += f"{indent}  Message: {_escape(err_msg)}\n"
            else:
                output += f"{indent}  {_escape(str(err))}\n"

        # --- System Fingerprint (OpenAI) ---
        fingerprint = response.get("system_fingerprint")
        if fingerprint:
            output += f"{indent}[dim]🔏 System: {_escape(fingerprint)}[/dim]\n"

        # --- Fallback: Show structure if nothing extracted ---
        if not output:
            keys = list(response.keys())[:10]
            output += (
                f"{indent}[dim]Response structure: {_escape(', '.join(keys))}[/dim]\n"
            )
            # Try to show first meaningful value
            for key in [
                "content",
                "text",
                "result",
                "data",
                "output",
                "answer",
                "response",
            ]:
                if key in response:
                    val = response[key]
                    if isinstance(val, str):
                        val_display = val[:300]
                    elif isinstance(val, (list, dict)):
                        val_display = f"({type(val).__name__} with {len(val)} items)"
                    else:
                        val_display = str(val)[:300]
                    output += f"{indent}[bold]{key}:[/bold] {_escape(val_display)}\n"
                    break

    except Exception as e:
        # Fallback with error info
        output = f"{indent}[dim]Could not parse response: {_escape(str(e))}[/dim]\n"
        output += f"{indent}{_escape(str(response)[:500])}\n"

    return output


def _format_config_dict(config: dict, indent: str = "  ") -> str:
    """Format a configuration dictionary for human-readable display.

    Args:
        config: Configuration dictionary
        indent: Indentation prefix

    Returns:
        Formatted string
    """
    if not config or not isinstance(config, dict):
        return f"{indent}[dim]<no config>[/dim]\n"

    output = ""
    for key, value in config.items():
        # Format based on value type
        if isinstance(value, bool):
            color = "bright_green" if value else "bright_red"
            output += (
                f"{indent}• [bold]{_escape(key)}:[/bold] [{color}]{value}[/{color}]\n"
            )
        elif isinstance(value, (int, float)):
            output += f"{indent}• [bold]{_escape(key)}:[/bold] [bright_cyan]{value}[/bright_cyan]\n"
        elif isinstance(value, str):
            # Truncate long strings
            display_val = value[:100] + "..." if len(value) > 100 else value
            output += f"{indent}• [bold]{_escape(key)}:[/bold] [yellow]{_escape(display_val)}[/yellow]\n"
        elif isinstance(value, list):
            if len(value) <= 5:
                items = [_escape(str(v)[:50]) for v in value]
                output += (
                    f"{indent}• [bold]{_escape(key)}:[/bold] [{', '.join(items)}]\n"
                )
            else:
                output += f"{indent}• [bold]{_escape(key)}:[/bold] [dim]({len(value)} items)[/dim]\n"
        elif isinstance(value, dict):
            output += f"{indent}• [bold]{_escape(key)}:[/bold] [dim]{{...}}[/dim]\n"
        else:
            output += (
                f"{indent}• [bold]{_escape(key)}:[/bold] {_escape(str(value)[:100])}\n"
            )

    return output


def _format_trace_content(content: Any, step_type: str, step_color: str) -> str:
    """Format trace content based on step type for human-readable display.

    Args:
        content: The trace content (dict, string, or other)
        step_type: The type of step (TOOL_CALL, TOOL_RESPONSE, etc.)
        step_color: Rich color for the step

    Returns:
        Formatted string for display
    """
    output = ""
    indent = f"[{step_color}]│[/]   "

    try:
        # Parse if string
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                # Plain text - show with wrapping
                lines = content.split("\n")[:15]
                for line in lines:
                    if line.strip():
                        output += f"{indent}{_escape(line[:200])}\n"
                return output

        if not isinstance(content, dict):
            return f"{indent}{_escape(str(content)[:500])}\n"

        # Format based on step type
        if step_type == "TOOL_CALL":
            # Tool name
            tool_name = (
                content.get("name")
                or content.get("tool")
                or content.get("function", {}).get("name")
            )
            if tool_name:
                output += f"[{step_color}]│[/] [bold bright_cyan]🔧 Tool:[/bold bright_cyan] [bright_white]{_escape(tool_name)}[/bright_white]\n"

            # Arguments
            args = (
                content.get("arguments")
                or content.get("input")
                or content.get("parameters")
            )
            if args:
                output += f"[{step_color}]│[/] [bold]Arguments:[/bold]\n"
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        pass

                if isinstance(args, dict):
                    for k, v in list(args.items())[:10]:
                        v_str = str(v)[:150]
                        output += (
                            f"{indent}[yellow]{_escape(k)}:[/yellow] {_escape(v_str)}\n"
                        )
                else:
                    output += f"{indent}{_escape(str(args)[:300])}\n"

        elif step_type == "TOOL_RESPONSE":
            # Result
            result = (
                content.get("result")
                or content.get("output")
                or content.get("response")
            )
            if result:
                output += f"[{step_color}]│[/] [bold bright_green]📤 Result:[/bold bright_green]\n"
                if isinstance(result, dict):
                    for k, v in list(result.items())[:10]:
                        v_str = str(v)[:150]
                        output += f"{indent}[bright_green]{_escape(k)}:[/bright_green] {_escape(v_str)}\n"
                elif isinstance(result, str):
                    lines = result.split("\n")[:10]
                    for line in lines:
                        if line.strip():
                            output += f"{indent}{_escape(line[:200])}\n"
                else:
                    output += f"{indent}{_escape(str(result)[:300])}\n"

            # Error if present
            error = content.get("error")
            if error:
                output += f"[{step_color}]│[/] [bold red]⚠️ Error:[/bold red] {_escape(str(error)[:200])}\n"

        elif step_type == "AGENT_THOUGHT":
            # Show thinking/reasoning
            thought = content.get("thought") or content.get("reasoning") or content
            if isinstance(thought, str):
                output += f"[{step_color}]│[/] [bold bright_magenta]💭 Thinking:[/bold bright_magenta]\n"
                lines = thought.split("\n")[:10]
                for line in lines:
                    if line.strip():
                        output += f"{indent}[italic]{_escape(line[:200])}[/italic]\n"
            elif isinstance(thought, dict):
                output += f"[{step_color}]│[/] [bold bright_magenta]💭 Thought:[/bold bright_magenta]\n"
                for k, v in list(thought.items())[:5]:
                    output += f"{indent}{_escape(k)}: {_escape(str(v)[:150])}\n"

        elif step_type == "AGENT_RESPONSE_CHUNK":
            # Show response text
            text = (
                content.get("content")
                or content.get("text")
                or content.get("response")
                or content
            )
            if isinstance(text, str):
                output += f"[{step_color}]│[/] [bold bright_white]💬 Response:[/bold bright_white]\n"
                lines = text.split("\n")[:15]
                for line in lines:
                    if line.strip():
                        output += f"{indent}{_escape(line[:200])}\n"
            elif isinstance(text, dict):
                # Handle structured response
                for k, v in list(text.items())[:5]:
                    output += f"{indent}{_escape(k)}: {_escape(str(v)[:150])}\n"

        elif step_type in ("MCP_STEP", "A2A_COMM"):
            # MCP or Agent-to-Agent communication
            action = (
                content.get("action") or content.get("type") or content.get("method")
            )
            if action:
                output += f"[{step_color}]│[/] [bold]Action:[/bold] [bright_yellow]{_escape(action)}[/bright_yellow]\n"

            target = (
                content.get("target") or content.get("server") or content.get("agent")
            )
            if target:
                output += f"[{step_color}]│[/] [bold]Target:[/bold] {_escape(target)}\n"

            data = (
                content.get("data") or content.get("payload") or content.get("message")
            )
            if data:
                output += f"[{step_color}]│[/] [bold]Data:[/bold]\n"
                if isinstance(data, dict):
                    for k, v in list(data.items())[:5]:
                        output += f"{indent}{_escape(k)}: {_escape(str(v)[:100])}\n"
                else:
                    output += f"{indent}{_escape(str(data)[:300])}\n"

        else:
            # Generic display - show key-value pairs nicely
            output += f"[{step_color}]│[/] [bold]Content:[/bold]\n"
            if isinstance(content, dict):
                for k, v in list(content.items())[:10]:
                    v_str = str(v)[:150]
                    output += (
                        f"{indent}[yellow]{_escape(k)}:[/yellow] {_escape(v_str)}\n"
                    )
                if len(content) > 10:
                    output += (
                        f"{indent}[dim]... ({len(content) - 10} more fields)[/dim]\n"
                    )
            else:
                output += f"{indent}{_escape(str(content)[:500])}\n"

    except Exception:
        # Fallback
        output = f"{indent}{_escape(str(content)[:500])}\n"

    return output


def _get_result_status_info(result: Any) -> tuple[str, str, str]:
    """Get status display info for a result.

    Args:
        result: Result object with evaluation_status

    Returns:
        Tuple of (eval_status, status_color, status_icon)
    """
    eval_status = "N/A"
    if hasattr(result, "evaluation_status"):
        eval_status = (
            result.evaluation_status.value
            if hasattr(result.evaluation_status, "value")
            else str(result.evaluation_status)
        )

    # Determine color and icon based on status
    if "SUCCESSFUL" in eval_status.upper() and "JAILBREAK" in eval_status.upper():
        status_color = "green"
        status_icon = "✅"
    elif "FAILED" in eval_status.upper() and "JAILBREAK" in eval_status.upper():
        status_color = "red"
        status_icon = "❌"
    elif "ERROR" in eval_status.upper():
        status_color = "red"
        status_icon = "⚠️"
    else:
        status_color = "yellow"
        status_icon = "ℹ️"

    return eval_status, status_color, status_icon


def _format_result_summary(result: Any, index: int) -> str:
    """Format a brief summary for a result's collapsible title.

    Args:
        result: Result object
        index: Result index (1-based)

    Returns:
        Formatted summary string for the collapsible title
    """
    eval_status, status_color, status_icon = _get_result_status_info(result)

    # Get prompt name if available (truncated)
    prompt_name = ""
    if hasattr(result, "prompt_name") and result.prompt_name:
        name = result.prompt_name
        if len(name) > 25:
            name = name[:22] + "..."
        prompt_name = f" 📝 {_escape(name)}"

    # Get latency if available - format nicely
    latency = ""
    if hasattr(result, "latency_ms") and result.latency_ms:
        ms = result.latency_ms
        if ms >= 1000:
            latency = f" ⏱️ {ms / 1000:.1f}s"
        else:
            latency = f" ⏱️ {ms}ms"

    # Get trace count with better formatting
    trace_count = ""
    if hasattr(result, "traces") and result.traces:
        count = len(result.traces)
        trace_count = f" 🔍 {count}"

    return f"{status_icon} [bold]#{index}[/bold] [{status_color}]{_escape(eval_status)}[/]{prompt_name}{latency}{trace_count}"


def _format_result_full_details(result: Any, index: int, max_traces: int = 5) -> str:
    """Format full details for a single result.

    Args:
        result: Result object
        index: Result index (1-based)
        max_traces: Maximum number of traces to display

    Returns:
        Formatted details string
    """
    eval_status, status_color, status_icon = _get_result_status_info(result)

    # Build compact header
    details = f"[dim]{'─' * 45}[/dim]\n"
    details += f"[bold]Result #{index}[/bold] {status_icon} [{status_color}]{_escape(eval_status)}[/]\n"
    details += f"[dim]ID: {str(result.id)[:8]}...[/dim]\n\n"

    # Key metrics in a compact row
    metrics_row = []
    if hasattr(result, "prompt_name") and result.prompt_name:
        metrics_row.append(f"📝 {_escape(result.prompt_name)[:30]}")
    if hasattr(result, "latency_ms") and result.latency_ms:
        ms = result.latency_ms
        if ms >= 1000:
            metrics_row.append(f"⏱️ {ms / 1000:.1f}s")
        else:
            metrics_row.append(f"⏱️ {ms}ms")
    if hasattr(result, "response_status_code") and result.response_status_code:
        code = result.response_status_code
        color = (
            "green" if 200 <= code < 300 else "yellow" if 300 <= code < 400 else "red"
        )
        metrics_row.append(f"[{color}]HTTP {code}[/]")

    if metrics_row:
        details += "  " + "  •  ".join(metrics_row) + "\n"

    # Show evaluation notes if any (compact)
    if hasattr(result, "evaluation_notes") and result.evaluation_notes:
        notes = result.evaluation_notes
        if len(notes) > 100:
            notes = notes[:97] + "..."
        details += f"\n  [dim]💬 {_escape(notes)}[/dim]\n"

    # Show evaluation metrics if any (compact inline)
    if hasattr(result, "evaluation_metrics") and result.evaluation_metrics:
        try:
            if (
                isinstance(result.evaluation_metrics, dict)
                and result.evaluation_metrics
            ):
                metrics_items = []
                for key, value in list(result.evaluation_metrics.items())[:3]:
                    metrics_items.append(
                        f"{_escape(key)}=[cyan]{_escape(str(value)[:15])}[/]"
                    )
                if metrics_items:
                    details += f"  📊 {' | '.join(metrics_items)}\n"
        except Exception:
            pass

    # Show request payload if available (collapsible-style)
    if hasattr(result, "request_payload") and result.request_payload:
        details += "\n[bold cyan]📤 Request[/bold cyan]\n"
        details += _format_request_payload(result.request_payload)

    # Show response body if available
    if hasattr(result, "response_body") and result.response_body:
        details += "\n[bold green]📥 Response[/bold green]\n"
        details += _format_response_body(result.response_body)

    # Show traces for this result
    if hasattr(result, "traces") and result.traces:
        # Sort traces by sequence number
        sorted_traces = sorted(
            result.traces,
            key=lambda t: t.sequence if hasattr(t, "sequence") else 0,
        )

        total_traces = len(sorted_traces)
        display_traces = sorted_traces[:max_traces]

        details += f"\n[bold magenta]🔍 Execution Traces[/bold magenta] [dim]({total_traces} steps)[/dim]\n"

        for trace in display_traces:
            # Get step type with proper field name
            step_type = "OTHER"
            step_icon = "📋"
            step_color = "cyan"

            if hasattr(trace, "step_type"):
                step_val = trace.step_type
                step_type = (
                    step_val.value if hasattr(step_val, "value") else str(step_val)
                )

                # Assign icons and colors based on step type
                if step_type == "TOOL_CALL":
                    step_icon = "🔧"
                    step_color = "green"
                elif step_type == "TOOL_RESPONSE":
                    step_icon = "📥"
                    step_color = "cyan"
                elif step_type == "AGENT_THOUGHT":
                    step_icon = "🧠"
                    step_color = "magenta"
                elif step_type == "AGENT_RESPONSE_CHUNK":
                    step_icon = "💬"
                    step_color = "white"
                elif step_type == "MCP_STEP":
                    step_icon = "🔗"
                    step_color = "yellow"
                elif step_type == "A2A_COMM":
                    step_icon = "🤝"
                    step_color = "yellow"

            # Get sequence number
            seq = trace.sequence if hasattr(trace, "sequence") else "?"

            # Get timestamp - compact format
            trace_time = ""
            if hasattr(trace, "timestamp"):
                try:
                    if isinstance(trace.timestamp, datetime):
                        trace_time = trace.timestamp.strftime("%H:%M:%S")
                    else:
                        dt = datetime.fromisoformat(
                            str(trace.timestamp).replace("Z", "+00:00")
                        )
                        trace_time = dt.strftime("%H:%M:%S")
                except Exception:
                    trace_time = str(trace.timestamp)[:8]

            # Format the trace header - more compact
            time_str = f" [dim]{trace_time}[/dim]" if trace_time else ""
            details += f"\n[{step_color}]┌[/] [{step_color}]{step_icon} Step {seq}[/] [bold]{_escape(step_type)}[/]{time_str}\n"

            # Get and format content using the helper function
            if hasattr(trace, "content") and trace.content:
                details += _format_trace_content(trace.content, step_type, step_color)

            details += f"[{step_color}]└{'─' * 35}[/]\n"

        # Show message if traces were truncated
        if total_traces > max_traces:
            details += f"\n[dim]... {total_traces - max_traces} more traces (export for full details)[/dim]\n"

    return details


class ResultsTab(Container):
    """Results tab for viewing attack results with split view."""

    DEFAULT_CSS = """
    ResultsTab {
        layout: horizontal;
    }
    
    ResultsTab #results-left-panel {
        width: 35%;
        border-right: solid $primary;
    }
    
    ResultsTab #results-right-panel {
        width: 65%;
    }
    
    ResultsTab #results-table {
        height: 100%;
    }
    
    ResultsTab #run-header-static {
        margin-bottom: 1;
        padding: 0 1;
    }
    
    ResultsTab #results-container {
        height: auto;
        padding: 0 1;
    }
    
    ResultsTab .result-collapsible {
        margin: 0 0 1 0;
        padding: 0;
    }
    
    ResultsTab .result-collapsible > CollapsibleTitle {
        padding: 1 2;
        background: $surface;
    }
    
    ResultsTab .result-collapsible.-success > CollapsibleTitle {
        background: $success-darken-3;
        color: $text;
    }
    
    ResultsTab .result-collapsible.-failed > CollapsibleTitle {
        background: $error-darken-3;
        color: $text;
    }
    
    ResultsTab .result-collapsible.-pending > CollapsibleTitle {
        background: $warning-darken-3;
        color: $text;
    }
    
    ResultsTab .result-details {
        padding: 1 2;
        margin: 0 0 1 0;
        background: $surface-darken-1;
    }
    
    ResultsTab .stats-bar {
        height: 3;
        margin: 1 0;
        padding: 0 1;
    }
    
    ResultsTab .success-bar {
        background: $success;
        height: 1;
    }
    
    ResultsTab .failed-bar {
        background: $error;
        height: 1;
    }
    """

    BINDINGS = [
        Binding("enter", "view_result", "View Details"),
        Binding("s", "show_summary", "Summary"),
        Binding("c", "toggle_compare", "Compare Runs"),
        Binding("d", "show_dashboard", "Dashboard"),
        Binding("pageup", "prev_page", "Previous Page", show=False),
        Binding("pagedown", "next_page", "Next Page", show=False),
        Binding("[", "prev_page", "Previous Page"),
        Binding("]", "next_page", "Next Page"),
    ]

    # Maximum number of results to display in detail view to prevent UI freeze
    MAX_RESULTS_DISPLAY = 10
    # Maximum number of traces per result to display
    MAX_TRACES_PER_RESULT = 5
    # Maximum content length for truncation
    MAX_CONTENT_LENGTH = 500

    def __init__(self, cli_config: CLIConfig):
        """Initialize results tab.

        Args:
            cli_config: CLI configuration object
        """
        super().__init__()
        self.cli_config = cli_config
        self.results_data: list[Any] = []
        self.selected_result: Any = None
        self._detail_page: int = 0  # Current page for result details pagination
        self._run_id_map: dict[str, Any] = {}  # Map run ID strings to run objects
        self._compare_runs: list[Any] = []  # Runs selected for comparison
        self._show_dashboard: bool = False  # Toggle dashboard view
        self._total_count: int = (
            0  # Total number of runs from API (for correct numbering)
        )

    def compose(self) -> ComposeResult:
        """Compose the results layout with horizontal split."""
        # Left side - Results list (30%)
        with VerticalScroll(id="results-left-panel"):
            yield Static(
                "[bold cyan]🎯 Attack Results[/bold cyan]",
                classes="section-header",
            )

            with Horizontal(classes="toolbar"):
                yield Button("🔄 Refresh", id="refresh-results", variant="primary")
                yield Button("📊 CSV", id="export-csv", variant="default")
                yield Button("📄 JSON", id="export-json", variant="default")
                yield Button("⚖️ Compare", id="compare-btn", variant="warning")
                yield Button("📈 Dashboard", id="dashboard-btn", variant="success")

            with Horizontal(classes="toolbar"):
                yield Label("Filter:")
                yield Select(
                    [
                        ("All", "all"),
                        ("Pending", "pending"),
                        ("Running", "running"),
                        ("Completed", "completed"),
                        ("Failed", "failed"),
                    ],
                    id="status-filter",
                    value="all",
                )
                yield Label("Limit:")
                yield Select(
                    [("10", "10"), ("25", "25"), ("50", "50"), ("100", "100")],
                    id="limit-select",
                    value="25",
                )

            # Results table
            yield DataTable(zebra_stripes=True, cursor_type="row", id="results-table")

        # Right side - Details view (70%)
        with VerticalScroll(id="results-right-panel"):
            yield Static(
                "[bold cyan]📋 Result Details[/bold cyan]",
                classes="section-header",
            )
            # Run header info (shows run overview when selected)
            yield Static(
                "[dim]💡 Select a run from the list to view details and results[/dim]",
                id="run-header-static",
            )
            # Container for collapsible result items
            yield Vertical(id="results-container")

    def on_mount(self) -> None:
        """Called when the tab is mounted."""
        # Initialize table columns with improved headers
        try:
            table = self.query_one("#results-table", DataTable)
            table.clear(columns=True)
            table.add_columns("#", "⚡", "Agent", "✅/❌", "Created")
        except Exception as e:
            self.app.notify(f"Failed to initialize table: {str(e)}", severity="error")

        # Show loading message immediately
        try:
            header_widget = self.query_one("#run-header-static", Static)
            header_widget.update("[cyan]Loading results from API...[/cyan]")
        except Exception:
            pass

        # Initial load - call refresh_data directly to populate initial state
        try:
            self.refresh_data()
        except Exception as e:
            # If initial load fails, show error
            try:
                header_widget = self.query_one("#run-header-static", Static)
                header_widget.update(
                    f"[red]Failed to load data: {_escape(str(e))}[/red]\n\n[dim]Press 🔄 Refresh button or F5 to retry[/dim]"
                )
            except Exception:
                pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "refresh-results":
            self.refresh_data()
        elif event.button.id == "export-csv":
            self._export_results_csv()
        elif event.button.id == "export-json":
            self._export_results_json()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle select dropdown changes."""
        if event.select.id in ["status-filter", "limit-select"]:
            self.refresh_data()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the results table."""
        row_key = event.row_key
        # The row key is the run ID string - use it to look up the run
        run_id_str = str(row_key.value) if hasattr(row_key, "value") else str(row_key)

        if run_id_str in self._run_id_map:
            self.selected_result = self._run_id_map[run_id_str]
            self._detail_page = 0  # Reset page when selecting new result
            self._show_result_details()

    def action_next_page(self) -> None:
        """Navigate to next page of results details."""
        if not self.selected_result:
            return
        run = self.selected_result
        if hasattr(run, "results") and run.results:
            total_results = len(run.results)
            total_pages = (
                total_results + self.MAX_RESULTS_DISPLAY - 1
            ) // self.MAX_RESULTS_DISPLAY
            if self._detail_page < total_pages - 1:
                self._detail_page += 1
                self._show_result_details()

    def action_prev_page(self) -> None:
        """Navigate to previous page of results details."""
        if self._detail_page > 0:
            self._detail_page -= 1
            self._show_result_details()

    def refresh_data(self) -> None:
        """Refresh results data from API."""
        try:
            from hackagent.api.run import run_list
            from hackagent.client import AuthenticatedClient

            # Get filter values
            status_sel = self.query_one("#status-filter", Select).value
            limit_sel = self.query_one("#limit-select", Select).value

            # Ensure we have strings (Select.value can be None/NoSelection)
            status_filter = str(status_sel) if status_sel is not None else "all"
            limit = 25
            if limit_sel is not None:
                try:
                    limit = int(str(limit_sel))
                except (ValueError, TypeError):
                    limit = 25

            # Validate configuration
            if not self.cli_config.api_key:
                self._show_empty_state("API key not configured")
                return

            import httpx

            client = AuthenticatedClient(
                base_url=self.cli_config.base_url,
                token=self.cli_config.api_key,
                prefix="Bearer",
                timeout=httpx.Timeout(5.0, connect=5.0),  # 5 second timeout
            )

            # Build query parameters with status filter if not "all"
            kwargs = {"client": client, "page_size": limit}
            if status_filter and status_filter != "all":
                # Map filter values to API enum
                from hackagent.models.run_list_status import RunListStatus

                status_map = {
                    "pending": RunListStatus.PENDING,
                    "running": RunListStatus.RUNNING,
                    "completed": RunListStatus.COMPLETED,
                    "failed": RunListStatus.FAILED,
                }
                if status_filter.lower() in status_map:
                    kwargs["status"] = status_map[status_filter.lower()]

            response = run_list.sync_detailed(**kwargs)

            if response.status_code == 200 and response.parsed:
                # Get all runs - these contain agent_name, attack info, etc.
                all_runs = response.parsed.results if response.parsed.results else []

                self.results_data = all_runs if all_runs else []
                # Store total count for correct run numbering
                self._total_count = (
                    response.parsed.count
                    if response.parsed.count
                    else len(self.results_data)
                )

                if not self.results_data:
                    self._show_empty_state(
                        "No runs found. Execute an attack to see results here."
                    )
                else:
                    self._update_table()
            elif response.status_code == 401:
                self._show_empty_state("Authentication failed")
            elif response.status_code == 403:
                self._show_empty_state("Access forbidden")
            else:
                self._show_empty_state(
                    f"Failed to fetch results: {response.status_code}"
                )

        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)

            # Provide helpful error messages
            if "timeout" in error_msg.lower() or "TimeoutException" in error_type:
                self._show_empty_state(
                    f"⚠️ Connection Timeout\n\n"
                    f"Cannot reach API: {self.cli_config.base_url}\n"
                    f"Check your network connection and retry."
                )
            elif "401" in error_msg or "authentication" in error_msg.lower():
                self._show_empty_state(
                    "🔒 Authentication Failed\n\nYour API key is invalid.\nRun: hackagent config set --api-key YOUR_KEY"
                )
            else:
                self._show_empty_state(
                    f"Error loading results: {error_type}\n{error_msg}"
                )

    def _show_empty_state(self, message: str) -> None:
        """Show an empty state message when no data is available.

        Args:
            message: Message to display
        """
        table = self.query_one("#results-table", DataTable)
        table.clear()

        # Show message in header area and clear results container
        header_widget = self.query_one("#run-header-static", Static)
        header_widget.update(
            f"[yellow]{_escape(message)}[/yellow]\n\n[dim]💡 Tip: Press F5 or click 🔄 Refresh to retry[/dim]"
        )

        # Clear results container
        results_container = self.query_one("#results-container", Vertical)
        results_container.remove_children()

    def _update_table(self) -> None:
        """Update the results table with current data."""
        try:
            table = self.query_one("#results-table", DataTable)
            table.clear()

            # Clear and rebuild the run ID mapping
            self._run_id_map.clear()

            # Sort runs by timestamp (oldest first) to assign stable numbers
            def get_timestamp(run):
                if hasattr(run, "timestamp") and run.timestamp:
                    if isinstance(run.timestamp, datetime):
                        return run.timestamp
                    try:
                        return datetime.fromisoformat(
                            str(run.timestamp).replace("Z", "+00:00")
                        )
                    except Exception:
                        pass
                return datetime.min

            sorted_runs = sorted(self.results_data, key=get_timestamp)

            # Calculate the starting number based on total count and displayed results
            # If we have 50 total runs and display 10, the oldest displayed run should be #41
            # The newest displayed run should be #50
            num_displayed = len(sorted_runs)
            start_number = self._total_count - num_displayed + 1

            # Create list of (run, stable_number) pairs, then reverse for display
            # so newest appears on top but oldest still has its correct global number
            numbered_runs = list(enumerate(sorted_runs, start=start_number))
            numbered_runs.reverse()  # Newest on top, oldest at bottom

            for idx, run in numbered_runs:
                # Get status with color coding from Run.status
                status_display = "Unknown"
                if hasattr(run, "status"):
                    status_val = run.status
                    if hasattr(status_val, "value"):
                        status_display = status_val.value
                    else:
                        status_display = str(status_val)

                    # Color code based on status - show only emoji
                    status_upper = status_display.upper()
                    if status_upper == "COMPLETED":
                        status_display = "[green]✅[/green]"
                    elif status_upper == "RUNNING":
                        status_display = "[cyan]🔄[/cyan]"
                    elif status_upper == "FAILED":
                        status_display = "[red]❌[/red]"
                    elif status_upper == "PENDING":
                        status_display = "[yellow]⏳[/yellow]"
                    else:
                        status_display = "[dim]❓[/dim]"

                # Get agent name - directly available in Run model
                agent_name = run.agent_name if hasattr(run, "agent_name") else "Unknown"
                # Truncate long agent names
                if len(agent_name) > 20:
                    agent_name = agent_name[:17] + "..."

                # Get created time from timestamp - show relative or compact time
                created_time = "N/A"
                if hasattr(run, "timestamp") and run.timestamp:
                    try:
                        dt = (
                            run.timestamp
                            if isinstance(run.timestamp, datetime)
                            else datetime.fromisoformat(
                                str(run.timestamp).replace("Z", "+00:00")
                            )
                        )
                        # Show more compact date
                        created_time = dt.strftime("%m/%d %H:%M")
                    except Exception:
                        created_time = str(run.timestamp)[:10]

                # Calculate success/failure ratio from results
                success_count = 0
                fail_count = 0
                total_results = 0
                if hasattr(run, "results") and run.results:
                    total_results = len(run.results)
                    for result in run.results:
                        if hasattr(result, "evaluation_status"):
                            eval_status = (
                                result.evaluation_status.value
                                if hasattr(result.evaluation_status, "value")
                                else str(result.evaluation_status)
                            )
                            if (
                                "SUCCESSFUL" in eval_status.upper()
                                and "JAILBREAK" in eval_status.upper()
                            ):
                                success_count += 1
                            elif (
                                "FAILED" in eval_status.upper()
                                and "JAILBREAK" in eval_status.upper()
                            ):
                                fail_count += 1

                # Format results as success/fail ratio with colors
                if total_results > 0:
                    results_display = (
                        f"[green]{success_count}[/green]/[red]{fail_count}[/red]"
                    )
                else:
                    results_display = "[dim]0/0[/dim]"

                # Get the run ID for stable row key lookup
                run_id_str = str(run.id) if hasattr(run, "id") else str(id(run))

                # Store in mapping for later lookup
                self._run_id_map[run_id_str] = run

                # Add row with columns: #, Status, Agent, Success/Fail, Created
                # Use the full run ID string as the row key for stable selection
                table.add_row(
                    str(idx),
                    status_display,
                    _escape(agent_name),
                    results_display,
                    created_time,
                    key=run_id_str,
                )

            # Calculate overall statistics
            total_success = 0
            total_failed = 0
            total_pending = 0
            for run in self.results_data:
                if hasattr(run, "results") and run.results:
                    for result in run.results:
                        if hasattr(result, "evaluation_status"):
                            eval_status = (
                                result.evaluation_status.value
                                if hasattr(result.evaluation_status, "value")
                                else str(result.evaluation_status)
                            )
                            if (
                                "SUCCESSFUL" in eval_status.upper()
                                and "JAILBREAK" in eval_status.upper()
                            ):
                                total_success += 1
                            elif (
                                "FAILED" in eval_status.upper()
                                and "JAILBREAK" in eval_status.upper()
                            ):
                                total_failed += 1
                            else:
                                total_pending += 1

            total_results = total_success + total_failed + total_pending
            success_rate = (
                (total_success / total_results * 100) if total_results > 0 else 0
            )

            # Show enhanced summary with visual success bar
            header_widget = self.query_one("#run-header-static", Static)

            # Create visual progress bar
            bar_width = 30
            success_blocks = int(
                (total_success / total_results * bar_width) if total_results > 0 else 0
            )
            failed_blocks = int(
                (total_failed / total_results * bar_width) if total_results > 0 else 0
            )
            pending_blocks = bar_width - success_blocks - failed_blocks

            progress_bar = (
                f"[green]{'█' * success_blocks}[/green]"
                f"[red]{'█' * failed_blocks}[/red]"
                f"[yellow]{'░' * pending_blocks}[/yellow]"
            )

            header_widget.update(
                f"[bold cyan]📊 Attack Results Summary[/bold cyan]\n"
                f"[dim]{'─' * 40}[/dim]\n\n"
                f"  [bold]Runs:[/bold] [bright_white]{len(self.results_data)}[/bright_white]    "
                f"[bold]Total Results:[/bold] [bright_white]{total_results}[/bright_white]\n\n"
                f"  {progress_bar}\n"
                f"  [green]✅ {total_success}[/green] successful   "
                f"[red]❌ {total_failed}[/red] failed   "
                f"[yellow]⏳ {total_pending}[/yellow] pending\n\n"
                f"  [bold]Success Rate:[/bold] [{'green' if success_rate >= 50 else 'yellow' if success_rate >= 25 else 'red'}]{success_rate:.1f}%[/]\n\n"
                f"[dim]💡 Click a row to view detailed results[/dim]"
            )

            # Clear results container when showing table
            results_container = self.query_one("#results-container", Vertical)
            results_container.remove_children()

        except Exception as e:
            # If table update fails, show error
            header_widget = self.query_one("#run-header-static", Static)
            header_widget.update(
                f"[red]❌ Error updating table: {_escape(str(e))}[/red]"
            )

    def _parse_agent_actions(self, logs_str: str) -> list[dict[str, Any]]:
        """Parse agent actions from log strings.

        Args:
            logs_str: Raw log string

        Returns:
            List of parsed action dictionaries
        """
        import re

        actions = []
        lines = logs_str.split("\n")

        for i, line in enumerate(lines):
            # HTTP requests
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

            # Tool/Function calls
            elif "Tool:" in line or "Function:" in line or "🔧" in line:
                tool_match = re.search(r"(?:Tool|Function):\s*([\w_]+)", line)
                if tool_match:
                    tool_name = tool_match.group(1)
                    # Look for arguments in next few lines
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

            # ADK events
            elif "ADK" in line and (
                "tool_call" in line.lower() or "tool_result" in line.lower()
            ):
                if "tool_call" in line.lower():
                    actions.append(
                        {"type": "adk_tool_call", "content": line, "line_num": i + 1}
                    )
                elif "tool_result" in line.lower():
                    actions.append(
                        {"type": "adk_tool_result", "content": line, "line_num": i + 1}
                    )

            # Model queries
            elif "Querying model" in line or "LLM" in line:
                model_match = re.search(r"model[\s:]+([\w-]+)", line)
                if model_match:
                    actions.append(
                        {
                            "type": "llm_query",
                            "model": model_match.group(1),
                            "line_num": i + 1,
                        }
                    )

        return actions

    def _show_result_details(self) -> None:
        """Show details of the selected run and its results using collapsible widgets.

        Each result is displayed as a collapsible item that expands on click.
        """
        if not self.selected_result:
            return

        run = self.selected_result  # This is a Run object now
        header_widget = self.query_one("#run-header-static", Static)
        results_container = self.query_one("#results-container", Vertical)

        # Show loading indicator immediately for responsive UI
        header_widget.update("[cyan]⏳ Loading run details...[/cyan]")
        results_container.remove_children()

        # Fetch full run details from API including all results and traces
        try:
            import httpx

            from hackagent.api.run import run_retrieve
            from hackagent.client import AuthenticatedClient

            client = AuthenticatedClient(
                base_url=self.cli_config.base_url,
                token=self.cli_config.api_key,
                prefix="Bearer",
                timeout=httpx.Timeout(10.0, connect=10.0),
            )

            run_id = run.id if isinstance(run.id, UUID) else UUID(str(run.id))
            response = run_retrieve.sync_detailed(client=client, id=run_id)

            if response.status_code == 200 and response.parsed:
                run = response.parsed
        except Exception as e:
            header_widget.update(
                f"[yellow]⚠️ Could not fetch full details: {_escape(str(e))}[/yellow]\n\n[dim]Showing cached data...[/dim]"
            )
            return

        # Format creation date
        created = "Unknown"
        if hasattr(run, "timestamp") and run.timestamp:
            try:
                if isinstance(run.timestamp, datetime):
                    created = run.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    created = str(run.timestamp)
            except (AttributeError, ValueError, TypeError):
                created = str(run.timestamp)

        # Get status from Run
        status_display = "Unknown"
        if hasattr(run, "status"):
            status_val = run.status
            if hasattr(status_val, "value"):
                status_display = status_val.value
            else:
                status_display = str(status_val)

        # Status color and icon based on status
        status_color = "yellow"
        status_icon = "🔄"
        if status_display.upper() == "COMPLETED":
            status_color = "green"
            status_icon = "✅"
        elif status_display.upper() == "FAILED":
            status_color = "red"
            status_icon = "❌"
        elif status_display.upper() == "RUNNING":
            status_color = "cyan"
            status_icon = "⚡"
        elif status_display.upper() == "PENDING":
            status_color = "yellow"
            status_icon = "⏳"

        # Get results count and evaluation summary
        results_count = (
            len(run.results) if hasattr(run, "results") and run.results else 0
        )

        # Count evaluation statuses
        eval_summary = {
            "SUCCESSFUL_JAILBREAK": 0,
            "FAILED_JAILBREAK": 0,
            "NOT_EVALUATED": 0,
            "ERROR": 0,
            "OTHER": 0,
        }
        if hasattr(run, "results") and run.results:
            for result in run.results:
                if hasattr(result, "evaluation_status"):
                    eval_status = (
                        result.evaluation_status.value
                        if hasattr(result.evaluation_status, "value")
                        else str(result.evaluation_status)
                    )
                    if (
                        "SUCCESSFUL" in eval_status.upper()
                        and "JAILBREAK" in eval_status.upper()
                    ):
                        eval_summary["SUCCESSFUL_JAILBREAK"] += 1
                    elif (
                        "FAILED" in eval_status.upper()
                        and "JAILBREAK" in eval_status.upper()
                    ):
                        eval_summary["FAILED_JAILBREAK"] += 1
                    elif "NOT_EVALUATED" in eval_status.upper():
                        eval_summary["NOT_EVALUATED"] += 1
                    elif "ERROR" in eval_status.upper():
                        eval_summary["ERROR"] += 1
                    else:
                        eval_summary["OTHER"] += 1

        # Build run header with visual progress bar
        total_evaluated = (
            eval_summary["SUCCESSFUL_JAILBREAK"] + eval_summary["FAILED_JAILBREAK"]
        )
        success_rate = (
            (eval_summary["SUCCESSFUL_JAILBREAK"] / total_evaluated * 100)
            if total_evaluated > 0
            else 0
        )

        # Create visual progress bar for this run
        bar_width = 25
        if results_count > 0:
            success_blocks = int(
                (eval_summary["SUCCESSFUL_JAILBREAK"] / results_count * bar_width)
            )
            failed_blocks = int(
                (eval_summary["FAILED_JAILBREAK"] / results_count * bar_width)
            )
            other_blocks = bar_width - success_blocks - failed_blocks
            progress_bar = (
                f"[green]{'█' * success_blocks}[/green]"
                f"[red]{'█' * failed_blocks}[/red]"
                f"[yellow]{'░' * other_blocks}[/yellow]"
            )
        else:
            progress_bar = f"[dim]{'░' * bar_width}[/dim]"

        header = f"""[bold cyan]╔{"═" * 50}╗[/bold cyan]
[bold cyan]║[/bold cyan] [bold bright_white]🎯 RUN DETAILS[/bold bright_white]{" " * 35}[bold cyan]║[/bold cyan]
[bold cyan]╚{"═" * 50}╝[/bold cyan]

[bold bright_cyan]▌ Overview[/bold bright_cyan]
  🆔 [bold]ID:[/bold]     [dim]{str(run.id)[:8]}...[/dim]
  🤖 [bold]Agent:[/bold]  [bright_cyan]{_escape(run.agent_name)}[/bright_cyan]
  🏢 [bold]Org:[/bold]    [bright_cyan]{_escape(run.organization_name)}[/bright_cyan]
  📅 [bold]Time:[/bold]   {_escape(created)}
  {status_icon} [bold]Status:[/bold] [bright_{status_color}]{_escape(status_display)}[/bright_{status_color}]

[bold bright_green]▌ Results Summary[/bold bright_green]
  {progress_bar}
  [green]✅ {eval_summary["SUCCESSFUL_JAILBREAK"]}[/green] success  [red]❌ {eval_summary["FAILED_JAILBREAK"]}[/red] failed  [yellow]⏳ {eval_summary["NOT_EVALUATED"] + eval_summary["OTHER"]}[/yellow] other
  
  [bold]Success Rate:[/bold] [{"bright_green" if success_rate >= 50 else "yellow" if success_rate >= 25 else "red"}]{success_rate:.1f}%[/]  [dim]({total_evaluated} evaluated)[/dim]
"""

        # Add run configuration if available
        if hasattr(run, "run_config") and run.run_config:
            header += "\n[bold bright_yellow]▌ Run Configuration[/bold bright_yellow]\n"
            try:
                if isinstance(run.run_config, dict):
                    header += _format_config_dict(run.run_config)
                else:
                    header += f"  {_escape(run.run_config)}\n"
            except Exception:
                header += f"  {_escape(run.run_config)}\n"

        # Add run notes if available
        if hasattr(run, "run_notes") and run.run_notes:
            header += (
                f"\n[bold magenta]▌ Notes[/bold magenta]\n  {_escape(run.run_notes)}\n"
            )

        # Update header widget
        header_widget.update(header)

        # Clear and rebuild results container with collapsible items
        results_container.remove_children()

        if hasattr(run, "results") and run.results:
            # Add results section header - more compact
            results_container.mount(
                Static(
                    f"\n[bold cyan]╔{'═' * 40}╗[/bold cyan]\n"
                    f"[bold cyan]║[/bold cyan] [bold]📋 Individual Results ({results_count})[/bold]{' ' * (26 - len(str(results_count)))}[bold cyan]║[/bold cyan]\n"
                    f"[bold cyan]╚{'═' * 40}╝[/bold cyan]\n"
                    f"[dim]Click any result to expand details[/dim]\n"
                )
            )

            # Create collapsible for each result
            for idx, result in enumerate(run.results, 1):
                # Get status info for CSS class
                eval_status, status_color, _ = _get_result_status_info(result)

                # Determine CSS class for status coloring
                css_class = "result-collapsible"
                if (
                    "SUCCESSFUL" in eval_status.upper()
                    and "JAILBREAK" in eval_status.upper()
                ):
                    css_class += " -success"
                elif (
                    "FAILED" in eval_status.upper()
                    and "JAILBREAK" in eval_status.upper()
                ):
                    css_class += " -failed"
                elif "ERROR" in eval_status.upper():
                    css_class += " -failed"
                else:
                    css_class += " -pending"

                # Create the title summary
                title = _format_result_summary(result, idx)

                # Create collapsible with full details inside
                collapsible = Collapsible(
                    Static(
                        _format_result_full_details(
                            result, idx, self.MAX_TRACES_PER_RESULT
                        ),
                        classes="result-details",
                    ),
                    title=title,
                    collapsed=True,
                    classes=css_class,
                )
                results_container.mount(collapsible)

            # Add tips at the bottom - compact
            results_container.mount(
                Static(
                    "\n[dim]─────────────────────────────────────[/dim]\n"
                    "[dim]💡 F5=Refresh • Export: CSV/JSON • Click row=select run[/dim]\n"
                )
            )

        else:
            # No results yet - show informative message
            self._show_no_results_message(run, status_display, results_container)

    def _show_no_results_message(
        self, run: Any, status_display: str, container: Vertical
    ) -> None:
        """Show appropriate message when run has no results.

        Args:
            run: The run object
            status_display: Current run status string
            container: Container to add the message to
        """
        message = "\n[bold yellow]⏳ No Results Yet[/bold yellow]\n"
        message += "[dim]─────────────────────────────────────[/dim]\n\n"

        if status_display == "PENDING":
            run_age = None
            if hasattr(run, "timestamp") and run.timestamp:
                try:
                    now = dt_module.datetime.now(tz.UTC)
                    run_timestamp = (
                        run.timestamp
                        if run.timestamp.tzinfo
                        else run.timestamp.replace(tzinfo=tz.UTC)
                    )
                    run_age = (now - run_timestamp).total_seconds() / 60
                except Exception:
                    pass

            if run_age and run_age > 5:
                message += "[bold yellow]⚠️  Stale Run Detected[/bold yellow]\n\n"
                message += f"[dim]This run was created {int(run_age)} minutes ago but has no results.[/dim]\n"
                message += "[dim]This typically means:[/dim]\n"
                message += (
                    "[dim]  • [bold]The client was interrupted or killed[/bold][/dim]\n"
                )
                message += "[dim]  • The attack process crashed before creating results[/dim]\n"
                message += "[dim]  • The run was never properly started[/dim]\n\n"
                message += "[bold red]⚡ Action Needed:[/bold red]\n"
                message += "[yellow]This run should be marked as FAILED or CANCELLED.[/yellow]\n"
                message += (
                    f"[dim]  hackagent run update {run.id} --status FAILED[/dim]\n"
                )
            else:
                message += "[bold yellow]⏳ This run is pending[/bold yellow]\n\n"
                message += "[dim]The attack has been initiated but results are not yet available.[/dim]\n"
                message += "[dim]Results will appear here once agent interactions complete.[/dim]\n"

        elif status_display == "RUNNING":
            message += "[bold cyan]🔄 Run is active[/bold cyan]\n\n"
            message += "[dim]Results will be added as the attack progresses...[/dim]\n"

        elif status_display == "COMPLETED":
            message += "[bold yellow]⚠️  Run completed with no results[/bold yellow]\n\n"
            message += "[dim]This might happen if:[/dim]\n"
            message += "[dim]  • The attack configuration didn't generate any test cases[/dim]\n"
            message += (
                "[dim]  • Agent calls failed before results could be created[/dim]\n"
            )

        elif status_display == "FAILED":
            message += "[bold red]❌ Run failed[/bold red]\n\n"
            message += "[dim]The run encountered errors before results could be created.[/dim]\n"

        else:
            message += (
                f"[bold yellow]Status: {_escape(status_display)}[/bold yellow]\n\n"
            )
            message += "[dim]No results have been recorded for this run yet.[/dim]\n"

        container.mount(Static(message))

    def _export_results_csv(self) -> None:
        """Export results to CSV file."""
        try:
            import csv
            from pathlib import Path

            if not self.results_data:
                self.notify("No results to export", severity="warning")
                return

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"hackagent_results_{timestamp}.csv"
            filepath = Path.cwd() / filename

            # Write CSV
            with open(filepath, "w", newline="") as csvfile:
                fieldnames = [
                    "ID",
                    "Agent",
                    "Attack Type",
                    "Status",
                    "Created",
                    "Duration",
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for result in self.results_data:
                    # Get status
                    status = "Unknown"
                    if hasattr(result, "evaluation_status"):
                        status_val = result.evaluation_status
                        status = (
                            status_val.value
                            if hasattr(status_val, "value")
                            else str(status_val)
                        )

                    # Get created date
                    created = "Unknown"
                    if hasattr(result, "created_at") and result.created_at:
                        created = str(result.created_at)

                    # Calculate duration
                    duration = "N/A"
                    if hasattr(result, "run") and result.run:
                        run = result.run
                        if (
                            hasattr(run, "started_at")
                            and run.started_at
                            and hasattr(run, "completed_at")
                            and run.completed_at
                        ):
                            try:
                                if isinstance(run.started_at, datetime) and isinstance(
                                    run.completed_at, datetime
                                ):
                                    delta = run.completed_at - run.started_at
                                    duration = f"{delta.total_seconds():.1f}s"
                            except Exception:
                                pass

                    writer.writerow(
                        {
                            "ID": str(result.id),
                            "Agent": getattr(result, "agent_name", "Unknown"),
                            "Attack Type": getattr(result, "attack_type", "Unknown"),
                            "Status": status,
                            "Created": created,
                            "Duration": duration,
                        }
                    )

            self.notify(
                f"✅ Exported {len(self.results_data)} results to {filename}",
                severity="information",
            )

        except Exception as e:
            self.notify(f"❌ Export failed: {str(e)}", severity="error")

    def _export_results_json(self) -> None:
        """Export results to JSON file."""
        try:
            from pathlib import Path

            if not self.results_data:
                self.notify("No results to export", severity="warning")
                return

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"hackagent_results_{timestamp}.json"
            filepath = Path.cwd() / filename

            # Convert results to dict
            results_list = []
            for result in self.results_data:
                result_dict = {
                    "id": str(result.id),
                    "agent_name": getattr(result, "agent_name", None),
                    "attack_type": getattr(result, "attack_type", None),
                    "created_at": str(result.created_at)
                    if hasattr(result, "created_at")
                    else None,
                }

                # Add status
                if hasattr(result, "evaluation_status"):
                    status_val = result.evaluation_status
                    result_dict["status"] = (
                        status_val.value
                        if hasattr(status_val, "value")
                        else str(status_val)
                    )

                # Add run information
                if hasattr(result, "run") and result.run:
                    result_dict["run"] = {
                        "id": str(result.run.id) if hasattr(result.run, "id") else None,
                        "status": str(result.run.status)
                        if hasattr(result.run, "status")
                        else None,
                        "started_at": str(result.run.started_at)
                        if hasattr(result.run, "started_at")
                        else None,
                        "completed_at": str(result.run.completed_at)
                        if hasattr(result.run, "completed_at")
                        else None,
                    }

                # Add config and data if available
                if hasattr(result, "attack_config"):
                    result_dict["attack_config"] = result.attack_config
                if hasattr(result, "data"):
                    result_dict["data"] = result.data
                if hasattr(result, "logs"):
                    result_dict["logs"] = str(result.logs)

                results_list.append(result_dict)

            # Write JSON
            with open(filepath, "w") as jsonfile:
                json.dump(
                    {
                        "exported_at": datetime.now().isoformat(),
                        "total_results": len(results_list),
                        "results": results_list,
                    },
                    jsonfile,
                    indent=2,
                )

            self.notify(
                f"✅ Exported {len(results_list)} results to {filename}",
                severity="information",
            )

        except Exception as e:
            self.notify(f"❌ Export failed: {str(e)}", severity="error")
