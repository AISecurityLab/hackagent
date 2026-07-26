# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Formatters for attack trace blocks and their step content."""

import json
from typing import Any

from hackagent.cli.tui.views.results.formatters.text import _escape


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
                    f"{indent}• [bold]{_escape(key)}:[/bold] \\[{', '.join(items)}]\n"
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
    step_num: int, step_type: str, content: dict, ts_str: str
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
        meta = content.get("metadata", {}) or {}
        result_inner = content.get("result", {}) or {}
        scorer_explanation = (
            content.get("scorer_explanation")
            or result_inner.get("scorer_explanation")
            or meta.get("scorer_explanation")
            or ""
        )
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
        if scorer_explanation:
            body += (
                f"  [dim]│[/dim]  [bold]Scorer:[/bold] "
                f"[dim]{_escape(scorer_explanation[:180])}[/dim]\n"
            )
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
