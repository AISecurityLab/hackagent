# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Past runs, as one tree you expand.

A campaign is what somebody ran, so a campaign is what a top-level line is.
Expanding it shows its attacks, and expanding an attack shows the goals it
tried and how each went. One screen, no panes: a terminal is narrow, and a
second pane halves the width of the one thing being read.

A run lives where its campaign's ``execution.storage`` put it, which is the
account or this machine. The view opens on whichever has runs, names it, and
reads the other on ``s``: the store being shown is a choice, never a guess
the reader has to make about why something is missing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from uuid import UUID

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Static, Tree
from textual.widgets.tree import TreeNode

from hackagent.evaluation.audit import AuditReport
from hackagent.interfaces.cli.config import CLIConfig
from hackagent.interfaces.audit import audit_summary
from hackagent.orchestrator.campaign.audit import format_report
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


@dataclass(frozen=True)
class _Store:
    """A place runs may have been recorded, and what to call it on screen."""

    label: str
    open: Callable[[], Any]


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
        Binding("s", "switch_store", "Switch store", show=False),
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
        #: The store on screen. Set by every refresh, and by the switch key,
        #: which is what makes it a choice rather than a guess.
        self._store_label: Optional[str] = None
        #: True once the user picked a store, after which the view stays
        #: there — an empty account they asked for is an answer.
        self._store_chosen = False

    def compose(self) -> ComposeResult:
        tree: Tree[Any] = Tree("runs", id="results-tree")
        tree.show_root = False
        tree.guide_depth = 2
        yield tree
        yield Static("", id="results-hint")

    # -- loading -------------------------------------------------------------

    def _stores(self) -> list["_Store"]:
        """The stores that may hold runs, in the order they are tried.

        Where a run was recorded is the campaign's choice, not the account's:
        a campaign records here unless it names a server, and an account can
        hold runs this machine has never seen. So the account is read first
        when there is one, and this machine after it.
        """
        stores = []
        if getattr(self.cli_config, "api_key", None):
            stores.append(_Store("the account", self.client))
        stores.append(_Store("this machine", self.local_client))
        return stores

    def refresh_data(self) -> None:
        """Read the store the user chose, or find one worth showing.

        Until a store is chosen, this looks for one with runs in it: an
        account that cannot be reached, or that has nothing, is no reason to
        show an empty screen while this machine holds what was just run.
        Once ``s`` has chosen one, that is the one read, empty or not.
        """
        hint = self.query_one("#results-hint", Static)
        stores = self._stores()
        if self._store_chosen:
            # Asked for by name: showing a different store instead would be
            # the very guessing the key exists to undo.
            stores = [
                store for store in stores if store.label == self._store_label
            ] or stores[:1]
        problems: list[tuple[str, str]] = []
        empty: Optional[_Store] = None
        for store in stores:
            try:
                loaded = self._read(store.open())
            except Exception as exc:
                problems.append((store.label, str(exc)))
                continue
            if loaded["campaigns"] or empty is None:
                self._apply(loaded)
            if loaded["campaigns"]:
                self._show(store.label, problems)
                return
            empty = empty or store
        if empty is not None:
            self._show(empty.label, problems)
            return
        # Whatever was on screen came from a store that is not being shown
        # any more; leaving it there would credit those runs to this one.
        self._clear()
        said = "; ".join(f"{label}: {message}" for label, message in problems)
        self._store_label = stores[0].label if stores else None
        switch = self._switch_hint(problems)
        hint.update(
            f"[$error]Could not read results — {_escape(said)}[/]"
            + (f" [dim]· {switch}[/dim]" if switch else "")
        )

    def _show(self, source: str, problems: Sequence[tuple[str, str]]) -> None:
        """Draw what was read, and say what could not be."""
        self._store_label = source
        self._build_tree(source, problems)
        for label, message in problems:
            self.notify(
                f"{label}: {message}", title="Results", severity="warning", timeout=8
            )

    def _switch_hint(self, problems: Sequence[tuple[str, str]] = ()) -> str:
        """``s: the other store``, or empty when there is only one.

        A store that failed is named here as failed, which is also why the
        view is showing the other one: one phrase answers both questions.
        """
        others = [
            store.label for store in self._stores() if store.label != self._store_label
        ]
        if not others:
            return ""
        failed = {label for label, _ in problems}
        unread = " (could not be read)" if others[0] in failed else ""
        return f"s: {_escape(others[0])}{unread}"

    def action_switch_store(self) -> None:
        """Read the other store — the account, or this machine."""
        stores = self._stores()
        if len(stores) < 2:
            self.notify(
                "Every run is recorded on this machine: no account is configured.",
                title="Results",
            )
            return
        labels = [store.label for store in stores]
        at = labels.index(self._store_label) if self._store_label in labels else 0
        self._store_label = labels[(at + 1) % len(labels)]
        self._store_chosen = True
        self.refresh_data()

    def _read(self, session: Any) -> dict[str, Any]:
        """Everything the tree needs from one store, or an exception.

        Nothing is assigned until the whole read succeeds, so a store that
        fails halfway cannot leave half of its runs on screen.
        """
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
        counts: dict[str, tuple] = {}
        results: dict[str, list[Any]] = {}
        for run in runs:
            try:
                run_id = run.id if isinstance(run.id, UUID) else UUID(str(run.id))
                items = list(
                    session.results(run_id=run_id, page=1, page_size=500).items
                )
            except Exception:
                items = []
            results[str(run.id)] = items
            outcomes = [
                classify_evaluation_status(getattr(r, "evaluation_status", None))
                for r in items
            ]
            counts[str(run.id)] = (
                sum(1 for o in outcomes if o is VULNERABLE),
                sum(1 for o in outcomes if o is MITIGATED),
                len(items),
            )
        return {
            "campaigns": campaigns,
            "runs": runs,
            "attacks": attacks,
            "agents": agents,
            "counts": counts,
            "results": results,
        }

    def _clear(self) -> None:
        """Show nothing: no store answered, so nothing can be attributed."""
        self._apply(
            {
                "campaigns": [],
                "runs": [],
                "attacks": {},
                "agents": {},
                "counts": {},
                "results": {},
            }
        )
        self.query_one("#results-tree", Tree).clear()

    def _apply(self, loaded: dict[str, Any]) -> None:
        self._campaigns = loaded["campaigns"]
        self.results_data = loaded["runs"]
        self._attack_map = loaded["attacks"]
        self._agent_map = loaded["agents"]
        self._result_counts = loaded["counts"]
        self._results_of_run = loaded["results"]

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

    def _build_tree(
        self, source: str = "", problems: Sequence[tuple[str, str]] = ()
    ) -> None:
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
            self._add_audit(node, getattr(campaign, "audit", None))
            for run in runs:
                self._add_attack(node, run)
        # Which store this is, and that there is another one, are part of
        # reading the list: runs recorded in an account that is down would
        # otherwise look as though they never happened.
        said = [f"{len(campaigns)} campaigns"]
        if source:
            said.append(_escape(source))
        if switch := self._switch_hint(problems):
            said.append(switch)
        said.append("enter expands · f5 refresh · ctrl+e CSV · ctrl+j JSON")
        self.query_one("#results-hint", Static).update(f"[dim]{' · '.join(said)}[/dim]")

    def _campaign_label(self, campaign: Any, runs: list[Any]) -> str:
        broken, goals, recorded = self._totals_of(runs)
        name = _escape(str(getattr(campaign, "name", None) or "untitled"))
        target = self._agent_map.get(str(getattr(campaign, "agent_id", "")), "")
        when = _ago(getattr(campaign, "created_at", None))
        trailer = f" · {_escape(target)}" if target else ""
        outcome = _outcome(broken, goals, getattr(campaign, "status", ""), recorded)
        label = f"[b]{name}[/b] · {when}{trailer}   {outcome}"
        audit = getattr(campaign, "audit", None)
        if audit:
            try:
                label += f"   {audit_summary(audit)}"
            except (TypeError, ValueError):
                pass
        return label

    def _add_audit(self, parent: TreeNode[Any], audit: Any) -> None:
        """The judge audit qualifies every attack of the campaign, so it sits first."""
        if not audit:
            return
        try:
            report = AuditReport.model_validate(dict(audit))
        except (TypeError, ValueError):
            return
        node = parent.add(f"[cyan]judge audit[/cyan] · {audit_summary(report)}")
        for line in format_report(report).splitlines():
            node.add_leaf(f"[dim]{_escape(line)}[/dim]")

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
