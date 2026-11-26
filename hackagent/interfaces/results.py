# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""What past runs found, said the same everywhere: the TUI's Results tree
and ``hackagent results summary`` read a store with :func:`read_outline`
and word its campaigns, attacks and goals with the functions here, as Rich
markup in the palette's colours.

A result's verdict is the reporting bucket every store records
(:func:`~hackagent.reporting.buckets.result_bucket`), in the log's words:
``jailbroken``, ``mitigated``, ``error``, ``no verdict``.
"""

from __future__ import annotations

import textwrap
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Optional

from rich.markup import escape

from hackagent.interfaces.palette import (
    ACCENT,
    PASSED,
    SECONDARY,
    UNDECIDED,
    VERDICT_STYLES,
    paint,
)
from hackagent.reporting.buckets import ERROR, JAILBREAK, MITIGATED, result_bucket

#: A result's verdict, by its bucket, in the words the log uses.
VERDICT_WORDS: dict[str, str] = {
    JAILBREAK: "jailbroken",
    MITIGATED: "mitigated",
    ERROR: "error",
}

#: Goals shown under one attack before the rest are summarised, and lines
#: of the target's reply shown under a goal.
MAX_GOALS, MAX_REPLY_LINES = 40, 6

#: An attack run's ``(jailbroken, mitigated, recorded)``.
Counts = tuple[int, int, int]


def read_outline(session: Any) -> dict[str, Any]:
    """The outline of a store: its campaigns and attack runs, and the names
    of its attacks and agents. Each attack run's results are read on their
    own (:func:`read_results`), being the slow part."""
    campaigns = list(session.campaign_runs(page=1, page_size=200).items)
    runs = list(session.runs(page=1, page_size=200).items)
    attacks = {
        str(attack.id): str(attack.type)
        for attack in session.attacks(page=1, page_size=500).items
    }
    agents = {
        str(agent.id): agent.name
        for agent in session.agents(page=1, page_size=500).items
    }
    return {"campaigns": campaigns, "runs": runs, "attacks": attacks, "agents": agents}


def read_results(session: Any, run: Any) -> list[Any]:
    """An attack run's results; none when they cannot be read."""
    from uuid import UUID

    try:
        run_id = run.id if isinstance(run.id, UUID) else UUID(str(run.id))
        return list(session.results(run_id=run_id, page=1, page_size=500).items)
    except Exception:
        return []


def newest_first(campaigns: Sequence[Any]) -> list[Any]:
    return sorted(
        campaigns, key=lambda c: str(getattr(c, "created_at", "")), reverse=True
    )


def runs_of(runs: Sequence[Any], campaign: Any) -> list[Any]:
    """The attack runs of a campaign."""
    return [
        run
        for run in runs
        if str(getattr(run, "campaign_run_id", "") or "") == str(campaign.id)
    ]


def verdict_of(result: Any) -> str:
    """A result's verdict: ``jailbroken``, ``mitigated``, ``error`` or
    ``no verdict``."""
    bucket = result_bucket(
        getattr(result, "evaluation_status", None),
        getattr(result, "evaluation_notes", None),
    )
    return VERDICT_WORDS.get(bucket, "no verdict")


def count(results: Sequence[Any]) -> Counts:
    """``(jailbroken, mitigated, recorded)`` of an attack run's results."""
    verdicts = [verdict_of(result) for result in results]
    return (
        verdicts.count("jailbroken"),
        verdicts.count("mitigated"),
        len(verdicts),
    )


def _coerce_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        when = value
    elif isinstance(value, (int, float)):
        when = datetime.fromtimestamp(float(value), tz=timezone.utc)
    else:
        try:
            when = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def ago(value: Any) -> str:
    """How long ago, in the words someone would use out loud."""
    when = _coerce_datetime(value)
    if when is None:
        return "—"
    seconds = (datetime.now(timezone.utc) - when).total_seconds()
    if seconds < 90:
        return "just now"
    for size, limit, suffix in ((60, 60, "m"), (3600, 24, "h"), (86400, 7, "d")):
        amount = int(seconds // size)
        if amount < limit:
            return f"{amount}{suffix} ago"
    return when.strftime("%d %b")


def outcome(broken: int, goals: int, status: str, recorded: int) -> str:
    """What came of it, or why nothing did."""
    state = (status or "").upper()
    if state in {"FAILED", "CANCELLED"} and not recorded:
        return paint("did not finish", UNDECIDED)
    if not recorded:
        return paint("nothing recorded", SECONDARY)
    total = goals or recorded
    if broken:
        return paint(
            f"{broken} of {total} goals jailbroken", VERDICT_STYLES["jailbroken"]
        )
    return paint(f"0 of {total} goals jailbroken", PASSED)


def outcome_of(runs: Sequence[Any], counted: Mapping[str, Counts], status: str) -> str:
    """What came of these attack runs; that they are being counted while
    any of them is."""
    broken = recorded = goals = 0
    for run in runs:
        counts = counted.get(str(run.id))
        if counts is None:
            return paint("counting…", SECONDARY)
        broken += counts[0]
        recorded += counts[2]
        config = getattr(run, "run_config", None) or {}
        try:
            goals += int(config.get("expected_total_goals") or 0)
        except (TypeError, ValueError):
            pass
    return outcome(broken, goals, status, recorded)


def campaign_line(
    campaign: Any,
    runs: Sequence[Any],
    counted: Mapping[str, Counts],
    agents: Mapping[str, str],
) -> str:
    """``name · when · target   what came of it   judges``."""
    from hackagent.interfaces.audit import audit_summary

    name = escape(str(getattr(campaign, "name", None) or "untitled"))
    target = agents.get(str(getattr(campaign, "agent_id", "")), "")
    when = ago(getattr(campaign, "created_at", None))
    trailer = f" · {escape(target)}" if target else ""
    said = outcome_of(runs, counted, getattr(campaign, "status", ""))
    line = f"[b]{name}[/b] · {when}{trailer}   {said}"
    audit = getattr(campaign, "audit", None)
    if audit:
        try:
            line += f"   {audit_summary(audit)}"
        except (TypeError, ValueError):
            pass  # a malformed audit leaves the line without its summary
    return line


def attack_line(
    run: Any, counted: Mapping[str, Counts], attacks: Mapping[str, str]
) -> str:
    """``attack   what came of it``."""
    name = attacks.get(str(getattr(run, "attack_id", "")), "attack")
    said = outcome_of([run], counted, getattr(run, "status", ""))
    return f"{escape(str(name)):<16}{said}"


def audit_lines(audit: Any) -> Optional[tuple[str, list[str]]]:
    """The judge audit's line and its table, when the campaign has one."""
    from hackagent.evaluation.audit import AuditReport
    from hackagent.interfaces.audit import audit_summary
    from hackagent.orchestrator.campaign.audit import format_report

    if not audit:
        return None
    try:
        report = AuditReport.model_validate(dict(audit))
    except (TypeError, ValueError):
        return None
    return (
        f"{paint('judge audit', ACCENT)} · {audit_summary(report)}",
        [paint(line, SECONDARY) for line in format_report(report).splitlines()],
    )


def goal_line(result: Any) -> str:
    """``verdict  the goal``: what the attack was trying to get, which is
    what makes the line worth reading."""
    goal = str(getattr(result, "goal", "") or "").replace("\n", " ")
    if len(goal) > 58:
        goal = goal[:55] + "…"
    word = verdict_of(result)
    return f"{paint(f'{word:<10}', VERDICT_STYLES.get(word, ''))}  {paint(goal, SECONDARY)}"


def reply_lines(result: Any, width: int = 86) -> list[str]:
    """What the target said, wrapped to a few lines: the evidence for the
    verdict."""
    metadata = getattr(result, "metadata", None) or {}
    reply = str(metadata.get("response") or "").strip()
    if not reply:
        notes = str(getattr(result, "evaluation_notes", "") or "").strip()
        reply = notes or "nothing recorded"
    wrapped = textwrap.wrap(reply.replace("\n", " "), width=width)
    lines = [paint(line, SECONDARY) for line in wrapped[:MAX_REPLY_LINES]]
    if len(wrapped) > MAX_REPLY_LINES:
        lines.append(paint("…", SECONDARY))
    return lines


def more_line(shown: int, total: int) -> Optional[str]:
    """That there are more goals than are shown."""
    if total <= shown:
        return None
    return paint(f"…{total - shown} more", SECONDARY)


__all__ = [
    "Counts",
    "MAX_GOALS",
    "VERDICT_WORDS",
    "ago",
    "attack_line",
    "audit_lines",
    "campaign_line",
    "count",
    "goal_line",
    "more_line",
    "newest_first",
    "outcome",
    "outcome_of",
    "read_outline",
    "read_results",
    "reply_lines",
    "runs_of",
    "verdict_of",
]
