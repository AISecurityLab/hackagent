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

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Collapsible, DataTable, Label, Select, Static

from hackagent.cli.config import CLIConfig
from hackagent.cli.tui.base import BaseTab


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


def _coerce_datetime(value: Any) -> datetime | None:
    """Best-effort conversion of API/local timestamp values to aware datetime."""
    if value is None:
        return None

    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(float(value), tz=dt_module.timezone.utc)
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=dt_module.timezone.utc)

    return dt


def _format_local_datetime(value: Any, fmt: str, fallback: str = "N/A") -> str:
    """Format timestamps in the machine local timezone for TUI display."""
    dt = _coerce_datetime(value)
    if dt is None:
        return fallback
    return dt.astimezone(tz.tzlocal()).strftime(fmt)


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


def _format_trace_block(
    step_num: int, seq: Any, step_type: str, content: dict, ts_str: str
) -> str:
    """Render one trace step block with semantic detection.

    Detects the logical sub-type from content keys and delegates to a
    specialised formatter, falling back to generic key-value display.
    """
    # Detect semantic sub-type from content structure
    evaluator = content.get("evaluator", "")
    step_name = content.get("step_name", "")
    has_goal = "goal" in content and "attack_type" in content

    if has_goal and not step_name:
        # ── Attack initialisation ──────────────────────────────────────────
        goal = content.get("goal", "")
        goal_index = content.get("goal_index", "?")
        attack = content.get("attack_type", "").upper()
        header = (
            f"  [bold cyan]{_step_num_circle(step_num)} 🎯 INIT[/bold cyan]{ts_str}"
        )
        body = (
            f"  [dim]│[/dim]  [bold]Attack:[/bold] [bright_white]{_escape(attack)}[/bright_white]\n"
            f"  [dim]│[/dim]  [bold]Goal #{goal_index}:[/bold] [yellow]{_escape(goal[:200])}[/yellow]\n"
        )
    elif evaluator == "HarmBenchEvaluator":
        # ── LLM judge evaluation ───────────────────────────────────────────
        score = content.get("score", "?")
        explanation = content.get("explanation", "")
        meta = content.get("metadata", {}) or {}
        judge_model = meta.get("judge_model", "")
        elapsed = meta.get("elapsed_s")
        completion = meta.get("completion")
        score_color = (
            "bright_green" if (isinstance(score, (int, float)) and score > 0) else "red"
        )
        elapsed_s = f"  [dim]{elapsed:.1f}s[/dim]" if elapsed is not None else ""
        header = f"  [bold magenta]{_step_num_circle(step_num)} ⚖️  LLM JUDGE[/bold magenta]{ts_str}"
        body = (
            f"  [dim]│[/dim]  [bold]Model:[/bold] [bright_cyan]{_escape(judge_model)}[/bright_cyan]{elapsed_s}\n"
            f"  [dim]│[/dim]  [bold]Score:[/bold] [{score_color}]{score}[/{score_color}]"
            f"  [dim]—[/dim]  {_escape(explanation[:120])}\n"
        )
        if completion:
            preview = completion[:100] + "…" if len(completion) > 100 else completion
            body += f"  [dim]│[/dim]  [bold]Completion:[/bold] [italic dim]{_escape(preview)}[/italic dim]\n"
        else:
            body += "  [dim]│[/dim]  [dim]Completion: (none / refused)[/dim]\n"
    elif (
        step_name == "Evaluation" and evaluator and evaluator != "tracking_coordinator"
    ):
        # ── Attack-specific evaluator ──────────────────────────────────────
        score = content.get("score", "?")
        explanation = content.get("explanation", "")
        result_inner = content.get("result", {}) or {}
        score_color = (
            "bright_green" if (isinstance(score, (int, float)) and score > 0) else "red"
        )
        header = f"  [bold yellow]{_step_num_circle(step_num)} 🔬 EVALUATOR[/bold yellow]{ts_str}"
        body = f"  [dim]│[/dim]  [bold]Type:[/bold] [dim]{_escape(evaluator)}[/dim]\n"
        # Render inner result fields
        for k, v in list(result_inner.items())[:6]:
            if isinstance(v, bool):
                vc = "bright_green" if v else "red"
                body += f"  [dim]│[/dim]    {_escape(k)}: [{vc}]{v}[/{vc}]\n"
            else:
                body += f"  [dim]│[/dim]    [yellow]{_escape(k)}:[/yellow] [{score_color}]{_escape(str(v))}[/{score_color}]\n"
        if explanation:
            body += f"  [dim]│[/dim]  [dim]{_escape(explanation[:150])}[/dim]\n"
    elif evaluator == "tracking_coordinator":
        # ── Coordinator summary ────────────────────────────────────────────
        result_inner = content.get("result", {}) or {}
        num_results = result_inner.get("num_results", "?")
        best_score = result_inner.get("best_score", 0.0)
        is_success = result_inner.get("is_success", False)
        jb_icon = (
            "[bright_green]✓ JAILBREAK[/bright_green]"
            if is_success
            else "[red]✗ REFUSED[/red]"
        )
        score_color = "bright_green" if best_score > 0 else "dim"
        header = f"  [bold green]{_step_num_circle(step_num)} 📋 SUMMARY[/bold green]{ts_str}"
        body = (
            f"  [dim]│[/dim]  Attempts: [bright_white]{num_results}[/bright_white]"
            f"  |  Best Score: [{score_color}]{best_score:.2f}[/{score_color}]"
            f"  |  {jb_icon}\n"
        )
    else:
        # ── Generic fallback (TOOL_CALL, AGENT_THOUGHT, etc.) ─────────────
        step_color, step_icon = _step_style(step_type)
        header = f"  [bold {step_color}]{_step_num_circle(step_num)} {step_icon} {_escape(step_type)}[/bold {step_color}]{ts_str}"
        body = _format_trace_content(content, step_type, step_color)

    return f"{header}\n{body}  [dim]{'╌' * 46}[/dim]\n"


def _step_num_circle(n: int) -> str:
    """Return a circled digit for step numbers 1–20."""
    circles = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
    if 1 <= n <= 20:
        return circles[n - 1]
    return f"({n})"


def _step_style(step_type: str) -> tuple[str, str]:
    """Return (rich_color, icon) for a step_type string."""
    mapping = {
        "TOOL_CALL": ("green", "🔧"),
        "TOOL_RESPONSE": ("cyan", "📥"),
        "AGENT_THOUGHT": ("magenta", "🧠"),
        "AGENT_RESPONSE_CHUNK": ("white", "💬"),
        "MCP_STEP": ("yellow", "🔗"),
        "A2A_COMM": ("yellow", "🤝"),
    }
    return mapping.get(step_type, ("bright_black", "📋"))


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

    # Goal text — prefer result.goal, fall back to metadata
    goal_text = ""
    raw_goal = getattr(result, "goal", None)
    if not raw_goal:
        raw_goal = (getattr(result, "metadata", None) or {}).get("goal", "")
    if raw_goal:
        truncated = raw_goal[:55] + "…" if len(raw_goal) > 55 else raw_goal
        goal_text = f"  [dim]{_escape(truncated)}[/dim]"

    # Timing from metadata
    timing = ""
    meta = getattr(result, "metadata", None) or {}
    elapsed = meta.get("elapsed_s")
    if elapsed is not None:
        try:
            timing = f"  [dim]⏱ {float(elapsed):.1f}s[/dim]"
        except (TypeError, ValueError):
            timing = ""

    # Best score from metadata
    score_str = ""
    best = meta.get("best_score")
    if best is not None:
        try:
            score_color = "bright_green" if float(best) > 0 else "dim"
            score_str = f"  [{score_color}]▸{float(best):.2f}[/{score_color}]"
        except (TypeError, ValueError):
            score_str = ""

    return f"{status_icon} [bold]#{index}[/bold] [{status_color}]{_escape(eval_status)}[/]{goal_text}{timing}{score_str}"


def _format_result_full_details(
    result: Any, index: int, max_traces: int = 5, traces: list | None = None
) -> str:
    """Format full details for a single result.

    Args:
        result: Result object
        index: Result index (1-based)
        max_traces: Maximum number of traces to display
        traces: Pre-fetched list of TraceRecord objects (used when result has no embedded traces)

    Returns:
        Formatted details string
    """
    eval_status, status_color, status_icon = _get_result_status_info(result)
    meta: dict = getattr(result, "metadata", None) or {}

    # ── Header ─────────────────────────────────────────────────────────────
    details = f"[bold {status_color}]{'━' * 48}[/bold {status_color}]\n"
    details += f"  {status_icon} [bold {status_color}]{_escape(eval_status)}[/bold {status_color}]"
    elapsed = meta.get("elapsed_s")
    if elapsed is not None:
        try:
            details += f"  [dim]⏱ {float(elapsed):.1f}s[/dim]"
        except (TypeError, ValueError):
            details += ""
    attack_type = meta.get("attack_type", "")
    # Try request_payload for attack_type
    if not attack_type:
        rp = getattr(result, "request_payload", None) or {}
        if isinstance(rp, dict):
            attack_type = rp.get("attack_type", "")
    if attack_type:
        details += f"  [dim]via {_escape(attack_type.upper())}[/dim]"
    details += "\n"
    details += f"[bold {status_color}]{'━' * 48}[/bold {status_color}]\n\n"

    # ── Goal ────────────────────────────────────────────────────────────────
    goal_text = getattr(result, "goal", None) or meta.get("goal", "")
    goal_index = getattr(result, "goal_index", None)
    if goal_text:
        gi_str = f"[dim] #{goal_index}[/dim]" if goal_index is not None else ""
        details += f"[bold cyan]🎯 GOAL{gi_str}[/bold cyan]\n"
        # Word-wrap goal at 80 chars
        words, line, wrapped = goal_text.split(), "", []
        for w in words:
            if len(line) + len(w) + 1 > 78:
                wrapped.append(line)
                line = w
            else:
                line = (line + " " + w).strip()
        if line:
            wrapped.append(line)
        for ln in wrapped:
            details += f"  [yellow]{_escape(ln)}[/yellow]\n"
        details += "\n"

    # ── Attack configuration ────────────────────────────────────────────────
    config_keys = [
        "flip_mode",
        "cot",
        "lang_gpt",
        "few_shot",
        "judge",
        "num_results",
        "best_score",
        "success",
        "total_traces",
    ]
    cfg_items = {k: meta[k] for k in config_keys if k in meta}
    if cfg_items:
        details += "[bold bright_yellow]⚙️  ATTACK CONFIG[/bold bright_yellow]\n"
        row_parts = []
        labels = {
            "flip_mode": "Mode",
            "cot": "CoT",
            "lang_gpt": "LangGPT",
            "few_shot": "FewShot",
            "judge": "Judge",
            "num_results": "Attempts",
            "best_score": "Best",
            "success": "Jailbreak",
            "total_traces": "Traces",
        }
        for k, v in cfg_items.items():
            label = labels.get(k, k)
            if isinstance(v, bool):
                val_s = "[bright_green]✓[/bright_green]" if v else "[dim]✗[/dim]"
            elif isinstance(v, float):
                val_s = f"[bright_cyan]{v:.2f}[/bright_cyan]"
            elif isinstance(v, str):
                val_s = f"[bright_white]{_escape(v)}[/bright_white]"
            else:
                val_s = f"[bright_cyan]{v}[/bright_cyan]"
            row_parts.append(f"[dim]{label}:[/dim] {val_s}")
        # 2-column layout
        for i in range(0, len(row_parts), 2):
            left = row_parts[i]
            right = row_parts[i + 1] if i + 1 < len(row_parts) else ""
            details += f"  {left:<50}{right}\n"
        details += "\n"

    # ── Evaluation notes ────────────────────────────────────────────────────
    notes = getattr(result, "evaluation_notes", None)
    if notes:
        details += f"[bold magenta]💬 NOTES[/bold magenta]\n  [italic dim]{_escape(notes[:200])}[/italic dim]\n\n"

    # ── Traces ──────────────────────────────────────────────────────────────
    _raw_traces = (
        (result.traces if hasattr(result, "traces") and result.traces else None)
        or traces
        or []
    )
    if _raw_traces:
        sorted_traces = sorted(
            _raw_traces,
            key=lambda t: t.sequence if hasattr(t, "sequence") else 0,
        )
        total_traces = len(sorted_traces)
        display_traces = sorted_traces[:max_traces]

        details += f"[bold magenta]🔍 EXECUTION TRACE[/bold magenta]  [dim]({total_traces} steps)[/dim]\n"
        details += f"[dim]{'─' * 48}[/dim]\n"

        for i, trace in enumerate(display_traces, 1):
            step_type = str(getattr(trace, "step_type", "OTHER"))
            if hasattr(getattr(trace, "step_type", None), "value"):
                step_type = trace.step_type.value
            content = getattr(trace, "content", {}) or {}
            seq = getattr(trace, "sequence", i)

            ts = getattr(trace, "timestamp", None) or getattr(trace, "created_at", None)
            ts_str = ""
            if ts:
                try:
                    _dt = (
                        ts
                        if isinstance(ts, datetime)
                        else datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                    )
                    ts_str = f"[dim] {_dt.strftime('%H:%M:%S')}[/dim]"
                except Exception:
                    pass

            details += _format_trace_block(i, seq, step_type, content, ts_str)

        if total_traces > max_traces:
            details += f"\n[dim]  … {total_traces - max_traces} more steps (use export for full trace)[/dim]\n"
    else:
        details += "[dim]  No execution traces recorded.[/dim]\n"

    return details


class ResultsTab(BaseTab):
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
        super().__init__(cli_config)
        self.results_data: list[Any] = []
        self.selected_result: Any = None
        self._detail_page: int = 0  # Current page for result details pagination
        self._run_id_map: dict[str, Any] = {}  # Map run ID strings to run objects
        self._compare_runs: list[Any] = []  # Runs selected for comparison
        self._show_dashboard: bool = False  # Toggle dashboard view
        self._total_count: int = (
            0  # Total number of runs from API (for correct numbering)
        )
        # Local-mode enrichment caches (populated in refresh_data)
        self._agent_map: dict[str, str] = {}  # agent_id str -> agent name
        self._attack_map: dict[str, str] = {}  # attack_id str -> attack type
        self._result_counts: dict[
            str, tuple
        ] = {}  # run_id str -> (success, fail, total)

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
            table.add_columns("#", "⚡", "Agent", "Attack", "✅/❌", "Created")
        except Exception as e:
            self.app.notify(f"Failed to initialize table: {str(e)}", severity="error")

        # Show loading message immediately
        try:
            header_widget = self.query_one("#run-header-static", Static)
            header_widget.update("[cyan]Loading results from API...[/cyan]")
        except Exception:
            pass

        # Do not fetch on mount; BaseTab.on_show will lazily trigger first refresh.
        # This prevents hidden tab network calls from delaying TUI startup.

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
            # Show summary in right panel
            self._show_result_summary(self.selected_result)
            self._show_result_details()

    def action_show_summary(self) -> None:
        """Show a quick summary for the selected run."""
        if self.selected_result:
            self._show_result_summary(self.selected_result)

    def _show_result_summary(self, run: Any) -> None:
        """Render a concise run summary in the right-side header panel."""
        header_widget = self.query_one("#run-header-static", Static)

        status_display = "Unknown"
        if hasattr(run, "status"):
            status_val = run.status
            status_display = (
                status_val.value if hasattr(status_val, "value") else str(status_val)
            )

        created = "Unknown"
        ts = getattr(run, "timestamp", None) or getattr(run, "created_at", None)
        if ts:
            created = _format_local_datetime(
                ts, fmt="%Y-%m-%d %H:%M:%S", fallback=str(ts)
            )

        run_cfg = getattr(run, "run_config", None)
        eval_summary = (
            run_cfg.get("evaluation_summary", {}) if isinstance(run_cfg, dict) else {}
        )
        total_attacks = int(eval_summary.get("total_attacks", 0) or 0)
        asr = float(eval_summary.get("overall_success_rate", 0.0) or 0.0) * 100.0
        mv_asr = float(eval_summary.get("majority_vote_asr", 0.0) or 0.0) * 100.0
        fleiss = eval_summary.get("fleiss_kappa")

        summary = (
            f"[bold cyan]▌ Selected Run[/bold cyan]\n"
            f"  🆔 [dim]{str(getattr(run, 'id', ''))[:8]}...[/dim]  "
            f"📅 {_escape(created)}  "
            f"Status: [bold]{_escape(status_display)}[/bold]\n"
        )
        if eval_summary:
            summary += (
                f"\n[bold bright_green]▌ Evaluation Summary[/bold bright_green]\n"
                f"  Total: [bold]{total_attacks}[/bold]  "
                f"ASR: [bold]{asr:.1f}%[/bold]  "
                f"Majority ASR: [bold]{mv_asr:.1f}%[/bold]"
            )
            if fleiss is not None:
                try:
                    summary += f"  Fleiss κ: [bold]{float(fleiss):.3f}[/bold]"
                except (TypeError, ValueError):
                    summary += f"  Fleiss κ: [bold]{_escape(str(fleiss))}[/bold]"
            summary += "\n"
        else:
            summary += "\n[dim]No evaluation summary synced yet for this run.[/dim]\n"

        header_widget.update(summary)

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

            # Validate configuration — works in local mode too
            pass

            backend = self.create_backend()

            # Fetch runs via backend
            runs_result = backend.list_runs(page=1, page_size=limit)
            all_runs = runs_result.items

            # Build agent name cache (for local RunRecord which only has agent_id)
            self._agent_map.clear()
            try:
                agents_result = backend.list_agents(page=1, page_size=500)
                for ag in agents_result.items:
                    self._agent_map[str(ag.id)] = ag.name
            except Exception:
                pass

            # Build attack type cache for showing human-readable attack names
            self._attack_map.clear()
            try:
                attacks_result = backend.list_attacks(page=1, page_size=500)
                for attack in attacks_result.items:
                    self._attack_map[str(attack.id)] = str(attack.type)
            except Exception:
                pass

            # Build result-count cache for runs that don't carry nested results
            self._result_counts.clear()
            for run in all_runs:
                if not hasattr(run, "results") or run.results is None:
                    try:
                        from uuid import UUID as _UUID

                        rid = (
                            run.id if isinstance(run.id, _UUID) else _UUID(str(run.id))
                        )
                        res_page = backend.list_results(
                            run_id=rid, page=1, page_size=500
                        )
                        success = sum(
                            1
                            for r in res_page.items
                            if "SUCCESSFUL"
                            in str(getattr(r, "evaluation_status", "")).upper()
                            and "JAILBREAK"
                            in str(getattr(r, "evaluation_status", "")).upper()
                        )
                        fail = sum(
                            1
                            for r in res_page.items
                            if "FAILED"
                            in str(getattr(r, "evaluation_status", "")).upper()
                            and "JAILBREAK"
                            in str(getattr(r, "evaluation_status", "")).upper()
                        )
                        self._result_counts[str(run.id)] = (
                            success,
                            fail,
                            len(res_page.items),
                        )
                    except Exception:
                        self._result_counts[str(run.id)] = (0, 0, 0)

            # Filter by status if requested
            if status_filter and status_filter != "all":
                all_runs = [
                    r
                    for r in all_runs
                    if str(r.status).upper() == status_filter.upper()
                ]

            self.results_data = all_runs if all_runs else []
            self._total_count = len(self.results_data)

            if not self.results_data:
                self._show_empty_state(
                    "No runs found. Execute an attack to see results here."
                )
            else:
                self._update_table()

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
                # Support both API response objects (timestamp) and RunRecord (created_at)
                ts = getattr(run, "timestamp", None) or getattr(run, "created_at", None)
                dt = _coerce_datetime(ts)
                if dt is not None:
                    return dt
                return datetime.min.replace(tzinfo=dt_module.timezone.utc)

            # Newest first; #1 is the most recent run by request.
            sorted_runs = sorted(self.results_data, key=get_timestamp, reverse=True)
            numbered_runs = list(enumerate(sorted_runs, start=1))

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

                # Get agent name — remote Run has agent_name, local RunRecord only has agent_id
                if hasattr(run, "agent_name") and run.agent_name:
                    agent_name = run.agent_name
                elif hasattr(run, "agent_id"):
                    agent_name = self._agent_map.get(
                        str(run.agent_id), str(run.agent_id)[:8] + "..."
                    )
                else:
                    agent_name = "Unknown"
                if len(agent_name) > 20:
                    agent_name = agent_name[:17] + "..."

                # Resolve attack name/type
                attack_name = "Unknown"
                run_cfg = getattr(run, "run_config", None)
                if isinstance(run_cfg, dict):
                    attack_name = str(
                        run_cfg.get("attack_type") or run_cfg.get("type") or attack_name
                    )

                attack_ref = getattr(run, "attack", None) or getattr(
                    run, "attack_id", None
                )
                if attack_ref:
                    attack_name = self._attack_map.get(str(attack_ref), attack_name)

                if len(attack_name) > 16:
                    attack_name = attack_name[:13] + "..."

                # Get created time — remote uses timestamp, local uses created_at
                created_time = "N/A"
                ts = getattr(run, "timestamp", None) or getattr(run, "created_at", None)
                if ts:
                    created_time = _format_local_datetime(
                        ts, fmt="%m/%d %H:%M", fallback=str(ts)[:10]
                    )

                # Calculate success/failure ratio — prefer nested results, fall back to cache
                if hasattr(run, "results") and run.results:
                    total_results = len(run.results)
                    success_count = sum(
                        1
                        for r in run.results
                        if "SUCCESSFUL"
                        in str(getattr(r, "evaluation_status", "")).upper()
                        and "JAILBREAK"
                        in str(getattr(r, "evaluation_status", "")).upper()
                    )
                    fail_count = sum(
                        1
                        for r in run.results
                        if "FAILED" in str(getattr(r, "evaluation_status", "")).upper()
                        and "JAILBREAK"
                        in str(getattr(r, "evaluation_status", "")).upper()
                    )
                else:
                    success_count, fail_count, total_results = self._result_counts.get(
                        str(run.id), (0, 0, 0)
                    )

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
                    _escape(attack_name),
                    results_display,
                    created_time,
                    key=run_id_str,
                )

            # Calculate overall statistics — use cached counts for local RunRecords
            total_success = 0
            total_failed = 0
            total_pending = 0
            for run in self.results_data:
                if hasattr(run, "results") and run.results:
                    for result in run.results:
                        eval_status = str(getattr(result, "evaluation_status", ""))
                        if hasattr(getattr(result, "evaluation_status", None), "value"):
                            eval_status = result.evaluation_status.value
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
                else:
                    s, f, t = self._result_counts.get(str(run.id), (0, 0, 0))
                    total_success += s
                    total_failed += f
                    total_pending += max(0, t - s - f)

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

        # Fetch full run details via backend
        try:
            from uuid import UUID

            backend = self.create_backend()
            run_id = run.id if isinstance(run.id, UUID) else UUID(str(run.id))
            run = backend.get_run(run_id)
        except Exception as e:
            header_widget.update(
                f"[yellow]⚠️ Could not fetch full details: {_escape(str(e))}[/yellow]\n\n[dim]Showing cached data...[/dim]"
            )
            return

        # Format creation date — remote uses timestamp, local uses created_at
        created = "Unknown"
        ts = getattr(run, "timestamp", None) or getattr(run, "created_at", None)
        if ts:
            created = _format_local_datetime(
                ts, fmt="%Y-%m-%d %H:%M:%S", fallback=str(ts)
            )

        # Resolve agent name — remote has agent_name, local has agent_id
        if hasattr(run, "agent_name") and run.agent_name:
            agent_display = run.agent_name
        elif hasattr(run, "agent_id"):
            agent_display = self._agent_map.get(
                str(run.agent_id), str(run.agent_id)[:8] + "..."
            )
        else:
            agent_display = "Unknown"

        # Resolve organisation name — local mode is always "Local"
        org_display = getattr(run, "organization_name", None) or "Local"

        # Fetch results for this run when they are not embedded (local RunRecord)
        run_results: list[Any] = []
        if hasattr(run, "results") and run.results:
            run_results = list(run.results)
        else:
            try:
                from uuid import UUID as _UUID

                _rid = run.id if isinstance(run.id, _UUID) else _UUID(str(run.id))
                _backend = self.create_backend()
                _res_page = _backend.list_results(run_id=_rid, page=1, page_size=500)
                run_results = list(_res_page.items)
            except Exception:
                pass

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
        results_count = len(run_results)

        # Count evaluation statuses
        eval_summary = {
            "SUCCESSFUL_JAILBREAK": 0,
            "FAILED_JAILBREAK": 0,
            "NOT_EVALUATED": 0,
            "ERROR": 0,
            "OTHER": 0,
        }
        for result in run_results:
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
  🤖 [bold]Agent:[/bold]  [bright_cyan]{_escape(agent_display)}[/bright_cyan]
  🏢 [bold]Org:[/bold]    [bright_cyan]{_escape(org_display)}[/bright_cyan]
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

        # Add synced evaluation summary metrics if available
        eval_summary = None
        if isinstance(getattr(run, "run_config", None), dict):
            eval_summary = run.run_config.get("evaluation_summary")
        if isinstance(eval_summary, dict) and eval_summary:
            total_attacks = int(eval_summary.get("total_attacks", 0) or 0)
            overall_asr = float(eval_summary.get("overall_success_rate", 0.0) or 0.0)
            majority_asr = float(eval_summary.get("majority_vote_asr", 0.0) or 0.0)
            fleiss_kappa = eval_summary.get("fleiss_kappa")
            strictness = eval_summary.get("per_judge_strictness")

            header += "\n[bold bright_green]▌ Evaluation Metrics[/bold bright_green]\n"
            header += (
                f"  • Total Attacks: [bold]{total_attacks}[/bold]\n"
                f"  • Overall ASR: [bold]{overall_asr * 100:.1f}%[/bold]\n"
                f"  • Majority-vote ASR: [bold]{majority_asr * 100:.1f}%[/bold]\n"
            )
            if fleiss_kappa is not None:
                try:
                    header += (
                        f"  • Fleiss' Kappa: [bold]{float(fleiss_kappa):.3f}[/bold]\n"
                    )
                except (TypeError, ValueError):
                    header += f"  • Fleiss' Kappa: [bold]{_escape(str(fleiss_kappa))}[/bold]\n"

            if isinstance(strictness, dict) and strictness:
                header += "  • Per-Judge Strictness:\n"
                for judge_name, judge_val in strictness.items():
                    try:
                        header += f"    - {_escape(str(judge_name))}: [bold]{float(judge_val):.3f}[/bold]\n"
                    except (TypeError, ValueError):
                        header += f"    - {_escape(str(judge_name))}: {_escape(str(judge_val))}\n"

        # Add run notes if available
        if hasattr(run, "run_notes") and run.run_notes:
            header += (
                f"\n[bold magenta]▌ Notes[/bold magenta]\n  {_escape(run.run_notes)}\n"
            )

        # Update header widget
        header_widget.update(header)

        # Clear and rebuild results container with collapsible items
        results_container.remove_children()

        if run_results:
            # Add results section header - more compact
            results_container.mount(
                Static(
                    f"\n[bold cyan]╔{'═' * 40}╗[/bold cyan]\n"
                    f"[bold cyan]║[/bold cyan] [bold]📋 Individual Results ({results_count})[/bold]{' ' * (26 - len(str(results_count)))}[bold cyan]║[/bold cyan]\n"
                    f"[bold cyan]╚{'═' * 40}╝[/bold cyan]\n"
                    f"[dim]Click any result to expand details[/dim]\n"
                )
            )

            # Pre-fetch traces for all results from the backend (local mode)
            _backend_for_traces = self.create_backend()
            _traces_by_result: dict[str, list] = {}
            for _r in run_results:
                try:
                    from uuid import UUID as _UUID2

                    _rid2 = _r.id if isinstance(_r.id, _UUID2) else _UUID2(str(_r.id))
                    _traces_by_result[str(_r.id)] = _backend_for_traces.list_traces(
                        _rid2
                    )
                except Exception:
                    _traces_by_result[str(_r.id)] = []

            # Create collapsible for each result
            for idx, result in enumerate(run_results, 1):
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

                # Resolve traces — embedded (remote) or pre-fetched (local)
                result_traces = _traces_by_result.get(str(result.id)) or []

                # Create the title summary (show trace count in header)
                trace_count_str = f" 🔍 {len(result_traces)}" if result_traces else ""
                title = _format_result_summary(result, idx) + trace_count_str

                # Create collapsible with full details inside
                collapsible = Collapsible(
                    Static(
                        _format_result_full_details(
                            result,
                            idx,
                            self.MAX_TRACES_PER_RESULT,
                            traces=result_traces,
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
