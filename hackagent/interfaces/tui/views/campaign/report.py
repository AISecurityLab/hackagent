# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The two summaries a run writes to its log: what it will do, and what it did.

Both are the tables ``hackagent campaign`` prints, in the markup the run view
writes. The numbers come from the campaign package — :func:`resolution_summary`
before the run and :func:`~hackagent.orchestrator.campaign.summary` after it —
so the terminal and the builder report a run the same way.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rich.markup import escape

#: The two numeric columns of the per-attack table, which are also as wide
#: as any count they hold.
_ATTEMPTS = "Attempts"
_SUCCESSES = "Successes"


def check_markup(rows: Mapping[str, str]) -> str:
    """The resolution summary, as a block of label-value lines."""
    if not rows:
        return ""
    width = max(len(label) for label in rows)
    lines = ["[bold cyan]▌ Campaign checks out[/bold cyan]"]
    lines += [
        f"  [dim]{escape(label.ljust(width))}[/dim]  {escape(str(value))}"
        for label, value in rows.items()
    ]
    return "\n".join(lines)


def attacks_markup(report: Mapping[str, Any]) -> str:
    """Attempts and successes per attack, the table ``campaign run`` prints.

    Empty when nothing ran — a dry run, or a campaign stopped before its
    first attack — where a table of no rows would say less than nothing.
    """
    attacks = list(report.get("attacks") or ())
    if not attacks:
        return ""
    width = max([len("Attack"), *(len(str(row.get("name", ""))) for row in attacks)])
    lines = [f"[dim]{'Attack'.ljust(width)}  {_ATTEMPTS}  {_SUCCESSES}  Error[/dim]"]
    for row in attacks:
        name = escape(str(row.get("name", "")).ljust(width))
        attempts = str(row.get("attempts", 0)).rjust(len(_ATTEMPTS))
        successes = int(row.get("successes") or 0)
        # A success is the target broken, which reads red here as everywhere.
        count = f"[red]{successes}[/red]" if successes else "[dim]0[/dim]"
        padded = " " * (len(_SUCCESSES) - len(str(successes))) + count
        error = str(row.get("error") or "")
        trailer = f"  [yellow]{escape(error)}[/yellow]" if error else ""
        lines.append(f"{name}  {attempts}  {padded}{trailer}")
    return "\n".join(lines)


__all__ = ["attacks_markup", "check_markup"]
