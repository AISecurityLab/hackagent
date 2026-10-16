# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Past runs, as one tree you expand.

A campaign is what somebody ran, so a campaign is what a top-level line is.
Expanding it shows its attacks, and expanding an attack shows the goals it
tried and how each went. One screen, no panes: a terminal is narrow, and a
second pane halves the width of the one thing being read.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Static, Tree
from textual.widgets.tree import TreeNode

from hackagent.interfaces.cli.config import CLIConfig
from hackagent.interfaces.tui.base import BaseTab
from hackagent.interfaces.tui.theme import (
    MITIGATED,
    VULNERABLE,
    classify_evaluation_status,
)
from hackagent.interfaces.tui.views.results.export import ResultsExportMixin
from hackagent.interfaces.tui.views.results.formatters import (
    _coerce_datetime,
    _escape,
)


def _ago(value: Any) -> str:
    """How long ago, in the words someone would use out loud."""
    when = _coerce_datetime(value)
    if when is None:
        return "—"
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    seconds = (datetime.now(timezone.utc) - when).total_seconds()
    if seconds < 90:
        return "just now"
    for size, limit, suffix in ((60, 60, "m"), (3600, 24, "h"), (86400, 7, "d")):
        count = int(seconds // size)
        if count < limit:
            return f"{count}{suffix} ago"
    return when.strftime("%d %b")


def _outcome(broken: int, goals: int, status: str, recorded: int) -> str:
    """What came of it, or why nothing did."""
    state = (status or "").upper()
    if state in {"FAILED", "CANCELLED"} and not recorded:
        return "[yellow]did not finish[/yellow]"
    if not recorded:
        return "[dim]nothing recorded[/dim]"
    total = goals or recorded
    if broken:
        return f"[red]{broken} of {total} goals jailbroken[/red]"
    return f"[green]0 of {total} goals jailbroken[/green]"


class ResultsTab(ResultsExportMixin, BaseTab):
    """Campaigns, their attacks, and the goals each attack tried."""

    DEFAULT_CSS = """
    ResultsTab { layout: vertical; }
    ResultsTab #results-tree { height: 1fr; padding: 0 1; }
    ResultsTab #results-hint {
        height: 1; padding: 0 1; color: $text-muted; background: $panel;
    }
    """

    BINDINGS = [
        Binding("f5", "refresh", "Refresh", show=False),
        Binding("ctrl+e", "export_csv", "Export CSV", show=False),
        Binding("ctrl+j", "export_json", "Export JSON", show=False),
    ]

    #: Goals listed under one attack before the rest are summarised.
    MAX_GOALS_SHOWN = 40
    #: Lines of the target's reply shown under a goal.
    MAX_REPLY_LINES = 6

    def __init__(self, cli_config: CLIConfig, **kwargs: Any) -> None:
        super().__init__(cli_config, **kwargs)
        self.results_data: list[Any] = []
        self.selected_result: Optional[Any] = None
        self._campaigns: list[Any] = []
        self._agent_map: dict[str, str] = {}
        self._attack_map: dict[str, str] = {}
        self._result_counts: dict[str, tuple] = {}
        self._results_of_run: dict[str, list[Any]] = {}

    def compose(self) -> ComposeResult:
        tree: Tree[Any] = Tree("runs", id="results-tree")
        tree.show_root = False
        tree.guide_depth = 2
        yield tree
        yield Static("", id="results-hint")

    # -- loading -------------------------------------------------------------

    def refresh_data(self) -> None:
        """Read the campaigns, their attacks and the results of each."""
        hint = self.query_one("#results-hint", Static)
        try:
            session = self.client()
            self._campaigns = list(session.campaign_runs(page=1, page_size=200).items)
            self.results_data = list(session.runs(page=1, page_size=200).items)

            self._attack_map = {
                str(attack.id): str(attack.type)
                for attack in session.attacks(page=1, page_size=500).items
            }
            self._agent_map = {
                str(agent.id): agent.name
                for agent in session.agents(page=1, page_size=500).items
            }

            self._result_counts.clear()
            self._results_of_run.clear()
            for run in self.results_data:
                try:
                    run_id = run.id if isinstance(run.id, UUID) else UUID(str(run.id))
                    items = session.results(run_id=run_id, page=1, page_size=500).items
                except Exception:
                    items = []
                self._results_of_run[str(run.id)] = items
                outcomes = [
                    classify_evaluation_status(getattr(r, "evaluation_status", None))
                    for r in items
                ]
                self._result_counts[str(run.id)] = (
                    sum(1 for o in outcomes if o is VULNERABLE),
                    sum(1 for o in outcomes if o is MITIGATED),
                    len(items),
                )
        except Exception as exc:
            hint.update(f"[$error]Could not read results: {_escape(str(exc))}[/]")
            return
        self._build_tree()

    # -- the tree ------------------------------------------------------------

    def _runs_of(self, campaign_id: str) -> list[Any]:
        return [
            run
            for run in self.results_data
            if str(getattr(run, "campaign_run_id", "") or "") == campaign_id
        ]

    def _totals_of(self, runs: list[Any]) -> tuple[int, int, int]:
        """``(jailbroken, goals, recorded)`` over these attack runs."""
        broken = recorded = goals = 0
        for run in runs:
            vulnerable, _mitigated, total = self._result_counts.get(
                str(run.id), (0, 0, 0)
            )
            broken += vulnerable
            recorded += total
            config = getattr(run, "run_config", None) or {}
            try:
                goals += int(config.get("expected_total_goals") or 0)
            except (TypeError, ValueError):
                pass
        return broken, goals, recorded

    def _build_tree(self) -> None:
        tree = self.query_one("#results-tree", Tree)
        tree.clear()
        campaigns = sorted(
            self._campaigns,
            key=lambda c: str(getattr(c, "created_at", "")),
            reverse=True,
        )
        for campaign in campaigns:
            runs = self._runs_of(str(campaign.id))
            node = tree.root.add(self._campaign_label(campaign, runs), expand=False)
            for run in runs:
                self._add_attack(node, run)
        self.query_one("#results-hint", Static).update(
            f"[dim]{len(campaigns)} campaigns · enter expands · f5 refresh · "
            "ctrl+e CSV · ctrl+j JSON[/dim]"
        )

    def _campaign_label(self, campaign: Any, runs: list[Any]) -> str:
        broken, goals, recorded = self._totals_of(runs)
        name = _escape(str(getattr(campaign, "name", None) or "untitled"))
        target = self._agent_map.get(str(getattr(campaign, "agent_id", "")), "")
        when = _ago(getattr(campaign, "created_at", None))
        trailer = f" · {_escape(target)}" if target else ""
        outcome = _outcome(broken, goals, getattr(campaign, "status", ""), recorded)
        return f"[b]{name}[/b] · {when}{trailer}   {outcome}"

    def _add_attack(self, parent: TreeNode[Any], run: Any) -> None:
        broken, goals, recorded = self._totals_of([run])
        name = self._attack_map.get(str(getattr(run, "attack_id", "")), "attack")
        outcome = _outcome(broken, goals, getattr(run, "status", ""), recorded)
        results = self._results_of_run.get(str(run.id), [])
        node = parent.add(f"{_escape(str(name)):<16}{outcome}", expand=False)
        for result in results[: self.MAX_GOALS_SHOWN]:
            goal = node.add(self._goal_label(result), expand=False)
            for line in self._reply_lines(result):
                goal.add_leaf(line)
        if len(results) > self.MAX_GOALS_SHOWN:
            node.add_leaf(
                f"[dim]…{len(results) - self.MAX_GOALS_SHOWN} more, "
                "export for the rest[/dim]"
            )

    def _goal_label(self, result: Any) -> str:
        outcome = classify_evaluation_status(getattr(result, "evaluation_status", None))
        # The goal is what the attack was trying to get, which is what makes
        # the line worth reading; the prompt it built is in the export.
        goal = str(getattr(result, "goal", "") or "").replace("\n", " ")
        if len(goal) > 58:
            goal = goal[:55] + "…"
        verdict = (
            f"[{VULNERABLE.color}]jailbroken[/{VULNERABLE.color}]"
            if outcome is VULNERABLE
            else f"[{MITIGATED.color}]held[/{MITIGATED.color}]"
            if outcome is MITIGATED
            else "[dim]not scored[/dim]"
        )
        return f"{verdict}  [dim]{_escape(goal)}[/dim]"

    def _reply_lines(self, result: Any) -> list[str]:
        """What the target actually said, wrapped to a few readable lines.

        One level deeper than the verdict, because the verdict is a claim and
        this is the evidence for it.
        """
        import textwrap

        metadata = getattr(result, "metadata", None) or {}
        reply = str(metadata.get("response") or "").strip()
        if not reply:
            notes = str(getattr(result, "evaluation_notes", "") or "").strip()
            reply = notes or "nothing recorded"
        wrapped = textwrap.wrap(reply.replace("\n", " "), width=86)
        lines = [
            f"[dim]{_escape(line)}[/dim]" for line in wrapped[: self.MAX_REPLY_LINES]
        ]
        if len(wrapped) > self.MAX_REPLY_LINES:
            # Appended after escaping, or the ellipsis brackets escape too.
            lines.append("[dim]…[/dim]")
        return lines

    # -- keys ----------------------------------------------------------------

    def action_refresh(self) -> None:
        self.refresh_data()

    def action_export_csv(self) -> None:
        self._export_results_csv()

    def action_export_json(self) -> None:
        self._export_results_json()


__all__ = ["ResultsTab"]
