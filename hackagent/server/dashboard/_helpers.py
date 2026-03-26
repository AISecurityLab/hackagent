# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Pure helper functions for the HackAgent dashboard (no NiceGUI dependency)."""

from __future__ import annotations

import contextlib
from datetime import datetime, timezone

_BRAND = "#dc2626"  # red-600


def _serialize(record) -> dict:
    return record.model_dump(mode="json")


def _rel_time(iso: str | None) -> str:
    if not iso:
        return "—"
    with contextlib.suppress(Exception):
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        diff = (datetime.now(timezone.utc) - dt).total_seconds()
        if diff < 60:
            return "just now"
        if diff < 3600:
            return f"{int(diff // 60)}m ago"
        if diff < 86400:
            return f"{int(diff // 3600)}h ago"
        if diff < 604_800:
            return f"{int(diff // 86400)}d ago"
        return dt.strftime("%b %d %Y")
    return iso or "—"


def _short_date(iso: str | None) -> str:
    """Return a compact date for table secondary timestamp rows."""
    if not iso:
        return "—"
    with contextlib.suppress(Exception):
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y")
    return "—"


def _duration_seconds(start_iso: str | None, end_iso: str | None) -> float | None:
    """Return duration in seconds between two ISO timestamps, or None."""
    if not start_iso or not end_iso:
        return None
    with contextlib.suppress(Exception):
        start_dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
        return max(0.0, (end_dt - start_dt).total_seconds())
    return None


def _format_latency(seconds: float | None) -> str:
    """Format seconds as a compact human-friendly latency string."""
    if seconds is None:
        return "—"
    if seconds < 1.0:
        return f"{int(round(seconds * 1000.0))}ms"
    if seconds < 60.0:
        return f"{seconds:.1f}s"
    total = int(round(seconds))
    minutes, sec = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m {sec:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m {sec:02d}s"


def _result_bucket(status: str | None, notes: str | None = None) -> str:
    """Classify a result into dashboard buckets.

    Buckets: jailbreak, mitigated, failed, pending.
    """
    s = (status or "").upper()
    n = (notes or "").lower()

    # Operational failures must be treated as failed even if the model outcome
    # would otherwise be considered mitigated.
    if "failed with exception" in n:
        return "failed"
    if "SUCCESSFUL_JAILBREAK" in s:
        return "jailbreak"
    if "FAILED_CRITERIA" in s or "ERROR" in s:
        return "failed"
    if "FAILED_JAILBREAK" in s or "PASSED_CRITERIA" in s:
        return "mitigated"
    if "NOT_EVALUATED" in s:
        return "pending"
    return "pending"


def _eval_label(status: str | None, notes: str | None = None) -> str:
    s = (status or "").upper()
    bucket = _result_bucket(status, notes)
    if bucket == "jailbreak":
        return "Jailbreak"
    if bucket == "mitigated":
        return "Mitigated"
    if bucket == "failed":
        return "Failed"
    if "ERROR_AGENT" in s:
        return "Failed"
    if bucket == "pending":
        return "Pending"
    return status or "N/A"


def _eval_color(status: str | None, notes: str | None = None) -> str:
    bucket = _result_bucket(status, notes)
    if bucket == "jailbreak":
        return "negative"
    if bucket == "mitigated":
        return "positive"
    if bucket == "failed":
        return "warning"
    return "grey-6"


def _step_color(step_type: str | None) -> str:
    s = (step_type or "").upper()
    if "TOOL_RESPONSE" in s:
        return "indigo"
    if "TOOL_CALL" in s:
        return "deep-purple"
    if "AGENT_THOUGHT" in s:
        return "blue"
    if "AGENT_RESPONSE" in s:
        return "green"
    if "MCP" in s:
        return "teal"
    if "A2A" in s:
        return "cyan"
    return "grey"
