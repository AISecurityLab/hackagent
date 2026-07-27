# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Formatters for HTTP request payloads and LLM response bodies."""

import json
from typing import Any

from hackagent.cli.tui.views.results.formatters.text import (
    _escape,
    _format_chat_message,
)


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
