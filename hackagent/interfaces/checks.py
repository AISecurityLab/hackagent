# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""How a campaign's check reads, in the TUI's builder and on the command
line alike: each problem where it is, how many there are to fix, or that
the campaign is ready to run and what it will run.

The problems are :func:`~hackagent.orchestrator.campaign.campaign_issues`;
this only says them, as Rich markup in the palette's colours.
"""

from __future__ import annotations

from rich.markup import escape

from hackagent.interfaces.palette import FAILED, PASSED, paint
from hackagent.orchestrator.campaign.check import Issue

#: What a campaign with nothing to fix is.
READY = "✓ ready to run"


def issue_markup(issue: Issue, *, relative_to: tuple = ()) -> str:
    """``✗ attacks.0: Unknown attack…``; the path from ``relative_to``
    when the reader is already there (a part of the builder)."""
    where = ".".join(str(part) for part in issue.loc[len(relative_to) :])
    said = f"{where}: {issue.message}" if where else issue.message
    return f"{paint('✗', FAILED)} {escape(said)}"


def to_fix_markup(count: int) -> str:
    """``✗ 2 to fix``."""
    return paint(f"✗ {count} to fix", FAILED)


def ready_markup(detail: str = "") -> str:
    """``✓ ready to run``, and what the campaign will run when known."""
    return paint(READY, PASSED) + (f" · {escape(detail)}" if detail else "")


__all__ = ["READY", "issue_markup", "ready_markup", "to_fix_markup"]
