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


def _eval_label(status: str | None) -> str:
    s = (status or "").upper()
    if "SUCCESSFUL_JAILBREAK" in s:
        return "Jailbreak"
    if "FAILED_JAILBREAK" in s:
        return "Mitigated"
    if "PASSED_CRITERIA" in s:
        return "Passed"
    if "FAILED_CRITERIA" in s:
        return "Failed"
    if "ERROR_AGENT" in s:
        return "Agent Error"
    if "ERROR" in s:
        return "Error"
    if "NOT_EVALUATED" in s:
        return "Pending"
    return status or "N/A"


def _eval_color(status: str | None) -> str:
    s = (status or "").upper()
    if "SUCCESSFUL_JAILBREAK" in s:
        return "negative"
    if "FAILED_JAILBREAK" in s or "PASSED_CRITERIA" in s:
        return "positive"
    if "ERROR" in s:
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
