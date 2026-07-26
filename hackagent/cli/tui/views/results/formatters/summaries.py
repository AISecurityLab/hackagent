# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Formatters for per-result summaries and full detail blocks."""

from datetime import datetime
from typing import Any

from hackagent.cli.tui.theme import classify_evaluation_status
from hackagent.cli.tui.views.results.formatters.text import _escape
from hackagent.cli.tui.views.results.formatters.traces import _format_trace_block


def _get_result_status_info(result: Any) -> tuple[str, str, str]:
    """Get status display info for a result.

    The label, colour and icon come from the shared defender-polarity
    vocabulary in :mod:`hackagent.cli.tui.theme`: a jailbreak that got through
    is a red ``Vulnerable`` result, not a green success.

    Args:
        result: Result object with evaluation_status

    Returns:
        Tuple of (status_label, status_color, status_icon)
    """
    outcome = classify_evaluation_status(getattr(result, "evaluation_status", None))
    return outcome.label, outcome.color, outcome.icon


def _format_result_summary(result: Any, index: int) -> str:
    """Format a brief summary for a result's collapsible title.

    Args:
        result: Result object
        index: Result index (1-based)

    Returns:
        Formatted summary string for the collapsible title
    """
    status_label, status_color, status_icon = _get_result_status_info(result)

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

    return f"{status_icon} [bold]#{index}[/bold] [{status_color}]{_escape(status_label)}[/]{goal_text}{timing}{score_str}"


def _format_result_full_details(
    result: Any, index: int, max_traces: int = 5, traces: list | None = None
) -> str:
    """Format full details for a single result with 3 sections: Result, Traces, Config.

    Mirrors the dashboard layout with tabbed sections.

    Args:
        result: Result object
        index: Result index (1-based)
        max_traces: Maximum number of traces to display
        traces: Pre-fetched list of TraceRecord objects

    Returns:
        Formatted details string
    """
    status_label, status_color, status_icon = _get_result_status_info(result)
    meta: dict = getattr(result, "metadata", None) or {}

    details = ""

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 1: RESULT
    # ══════════════════════════════════════════════════════════════════════
    details += "[bold bright_cyan]┌─ 📋 Result ──────────────────────────────────┐[/bold bright_cyan]\n\n"

    # Status + timing
    details += f"  {status_icon} [bold {status_color}]{_escape(status_label)}[/bold {status_color}]"
    elapsed = meta.get("elapsed_s")
    if elapsed is not None:
        try:
            details += f"  [dim]⏱ {float(elapsed):.1f}s[/dim]"
        except (TypeError, ValueError):
            pass
    attack_type = meta.get("attack_type", "")
    if not attack_type:
        rp = getattr(result, "request_payload", None) or {}
        if isinstance(rp, dict):
            attack_type = rp.get("attack_type", "")
    if attack_type:
        details += f"  [dim]via {_escape(attack_type.upper())}[/dim]"
    details += "\n\n"

    # Goal
    goal_text = getattr(result, "goal", None) or meta.get("goal", "")
    goal_index = getattr(result, "goal_index", None)
    if goal_text:
        gi_str = f" #{goal_index}" if goal_index is not None else ""
        details += f"  [dim]GOAL{gi_str}:[/dim]\n"
        words, line, wrapped = goal_text.split(), "", []
        for w in words:
            if len(line) + len(w) + 1 > 76:
                wrapped.append(line)
                line = w
            else:
                line = (line + " " + w).strip()
        if line:
            wrapped.append(line)
        for ln in wrapped:
            details += f"    [yellow]{_escape(ln)}[/yellow]\n"
        details += "\n"

    # Evaluation notes
    notes = getattr(result, "evaluation_notes", None)
    if notes:
        details += f"  [dim]Evaluation Notes:[/dim]\n    [italic]{_escape(notes[:300])}[/italic]\n\n"

    # Key metrics table
    metric_keys = [
        ("elapsed_s", "Elapsed", lambda v: f"{float(v):.1f}s"),
        ("objective", "Objective", str),
        (
            "best_score",
            "Best Score",
            lambda v: f"{float(v):.2f}" if isinstance(v, (int, float)) else str(v),
        ),
        (
            "success",
            "Success",
            lambda v: "[green]✓ Yes[/green]" if v else "[red]✗ No[/red]",
        ),
        ("goal_index", "Goal Index", str),
        ("n_iterations", "Iterations Config", str),
        ("iterations_completed", "Iterations Done", str),
        ("total_traces", "Total Traces", str),
    ]
    shown = []
    for key, label, fmt in metric_keys:
        val = meta.get(key)
        if val is not None:
            try:
                shown.append((label, fmt(val)))
            except (TypeError, ValueError):
                shown.append((label, str(val)))
    if shown:
        details += "  [dim]─── Key Metrics ───[/dim]\n"
        for label, val in shown:
            details += f"  [dim]{label}:[/dim] {val}\n"
        details += "\n"

    # Jailbreak prompt/response (when available — e.g. advprefix, PAIR)
    jb_prompt = meta.get("jailbreak_prompt") or meta.get("best_prompt", "")
    jb_response = meta.get("jailbreak_response") or meta.get("best_response", "")
    if jb_prompt or jb_response:
        details += "  [bold red]─── Jailbreak Details ───[/bold red]\n"
        if jb_prompt:
            details += "  [dim]Prompt:[/dim]\n"
            prompt_preview = jb_prompt[:500]
            for p_line in prompt_preview.split("\n")[:8]:
                details += (
                    f"    [bright_yellow]{_escape(p_line[:120])}[/bright_yellow]\n"
                )
            if len(jb_prompt) > 500:
                details += f"    [dim]... ({len(jb_prompt) - 500} more chars)[/dim]\n"
            details += "\n"
        if jb_response:
            details += "  [dim]Response:[/dim]\n"
            resp_preview = jb_response[:500]
            for r_line in resp_preview.split("\n")[:8]:
                details += f"    [bright_red]{_escape(r_line[:120])}[/bright_red]\n"
            if len(jb_response) > 500:
                details += f"    [dim]... ({len(jb_response) - 500} more chars)[/dim]\n"
            details += "\n"

    details += "[bold bright_cyan]└──────────────────────────────────────────────┘[/bold bright_cyan]\n\n"

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 2: TRACES
    # ══════════════════════════════════════════════════════════════════════
    _raw_traces = (
        (result.traces if hasattr(result, "traces") and result.traces else None)
        or traces
        or []
    )

    details += f"[bold bright_magenta]┌─ 🔍 Traces ({len(_raw_traces)}) ────────────────────────────┐[/bold bright_magenta]\n\n"

    if _raw_traces:
        sorted_traces = sorted(
            _raw_traces,
            key=lambda t: t.sequence if hasattr(t, "sequence") else 0,
        )
        total_traces = len(sorted_traces)
        display_traces = sorted_traces[:max_traces]

        for i, trace in enumerate(display_traces, 1):
            step_type = str(getattr(trace, "step_type", "OTHER"))
            if hasattr(getattr(trace, "step_type", None), "value"):
                step_type = trace.step_type.value
            content = getattr(trace, "content", {}) or {}

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

            details += _format_trace_block(i, step_type, content, ts_str)

        if total_traces > max_traces:
            details += f"\n  [dim]… {total_traces - max_traces} more steps (use export for full trace)[/dim]\n"
    else:
        details += "  [dim]No execution traces recorded.[/dim]\n"

    details += "\n[bold bright_magenta]└──────────────────────────────────────────────┘[/bold bright_magenta]\n\n"

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 3: CONFIG
    # ══════════════════════════════════════════════════════════════════════
    details += "[bold bright_yellow]┌─ ⚙️  Config ─────────────────────────────────┐[/bold bright_yellow]\n\n"

    config_keys = [
        "flip_mode",
        "cot",
        "lang_gpt",
        "few_shot",
        "judge",
        "num_results",
        "attack_type",
        "program",
        "syntax_version",
        "objective",
        "n_iterations",
    ]
    cfg_items = {k: meta[k] for k in config_keys if k in meta}
    if cfg_items:
        labels = {
            "flip_mode": "Mode",
            "cot": "CoT",
            "lang_gpt": "LangGPT",
            "few_shot": "FewShot",
            "judge": "Judge",
            "num_results": "Attempts",
            "attack_type": "Attack Type",
            "program": "Program",
            "syntax_version": "Syntax Version",
            "objective": "Objective",
            "n_iterations": "N Iterations",
        }
        for k, v in cfg_items.items():
            label = labels.get(k, k)
            if isinstance(v, bool):
                val_s = "[green]✓[/green]" if v else "[dim]✗[/dim]"
            elif isinstance(v, float):
                val_s = f"[bright_cyan]{v:.2f}[/bright_cyan]"
            elif isinstance(v, str):
                val_s = f"[bright_white]{_escape(v[:80])}[/bright_white]"
            else:
                val_s = f"[bright_cyan]{v}[/bright_cyan]"
            details += f"  [dim]{label}:[/dim] {val_s}\n"
    else:
        details += "  [dim]No configuration metadata available.[/dim]\n"

    details += "\n[bold bright_yellow]└──────────────────────────────────────────────┘[/bold bright_yellow]\n"

    return details
