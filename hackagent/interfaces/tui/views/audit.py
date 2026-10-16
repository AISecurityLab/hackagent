# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Rich markup for judge audits shown by TUI run and result views."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rich.markup import escape

from hackagent.evaluation.audit import AuditReport
from hackagent.orchestrator.campaign.audit import format_report


def audit_markup(value: AuditReport | Mapping[str, Any]) -> str:
    """Render a complete audit table from a live or persisted report."""

    report = (
        value
        if isinstance(value, AuditReport)
        else AuditReport.model_validate(dict(value))
    )
    state = {
        True: "[bold green]passed[/bold green]",
        False: "[bold red]FAILED[/bold red]",
        None: "[bold yellow]not graded[/bold yellow]",
    }[report.passed]
    return (
        f"[bold cyan]▌ Judge audit[/bold cyan] · {state}\n"
        f"[dim]{escape(format_report(report))}[/dim]"
    )


__all__ = ["audit_markup"]
