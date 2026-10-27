# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Rich markup for judge audits shown by the CLI and TUI run and result views."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rich.markup import escape

from hackagent.evaluation.audit import AuditReport
from hackagent.orchestrator.campaign.audit import format_report


def audit_markup(value: AuditReport | Mapping[str, Any]) -> str:
    """Render a complete audit table from a live or persisted report."""

    report = _report(value)
    state = {
        True: "[bold green]passed[/bold green]",
        False: "[bold red]FAILED[/bold red]",
        None: "[bold yellow]not graded[/bold yellow]",
    }[report.passed]
    return (
        f"[bold cyan]▌ Judge audit[/bold cyan] · {state}\n"
        f"[dim]{escape(format_report(report))}[/dim]"
    )


def _report(value: AuditReport | Mapping[str, Any]) -> AuditReport:
    if isinstance(value, AuditReport):
        return value
    return AuditReport.model_validate(dict(value))


def audit_summary(value: AuditReport | Mapping[str, Any]) -> str:
    """One line for a run listing: verdict, panel accuracy and robustness."""

    report = _report(value)
    state = {
        True: "[green]judges passed[/green]",
        False: "[red]judges FAILED[/red]",
        None: "[yellow]judges not graded[/yellow]",
    }[report.passed]
    parts = [state]
    if report.judges:
        panel = report.judges[-1]
        parts.append(f"acc {panel.metrics.accuracy:.3f}")
        if panel.robustness is not None:
            parts.append(f"flips {panel.robustness.any_wrapper_flip_rate:.1%}")
    return " · ".join(parts)


__all__ = ["audit_markup", "audit_summary"]
