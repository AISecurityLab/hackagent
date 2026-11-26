# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Past runs, as one tree you expand.

A campaign is what somebody ran, so a campaign is what a top-level line is.
Expanding it shows its attacks, and expanding an attack shows the goals it
tried and how each went. One screen, no panes: a terminal is narrow, and a
second pane halves the width of the one thing being read.

Opening it never waits for the store. Campaigns and their attacks are read
first, on a thread of their own, and drawn at once; each attack's results
are read after, newest campaign first, and its counts filled in as they
arrive. An attack's goals become nodes only when it is expanded.

A run lives where its campaign's ``execution.storage`` put it, which is the
account or this machine. The view opens on whichever has runs, names it, and
reads the other on ``s``: the store being shown is a choice, never a guess
the reader has to make about why something is missing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Callable, Optional

from rich.markup import escape
from textual.app import ComposeResult
from textual.widgets import Static, Tree
from textual.widgets.tree import TreeNode

from hackagent.core.settings import Mode, Settings
from hackagent.interfaces.cli.config import CLIConfig
from hackagent.interfaces.tui.base import BaseTab
from hackagent.interfaces.palette import (
    SECONDARY,
    paint,
)
from hackagent.interfaces.tui.frame import title_bar
from hackagent.interfaces.tui.keys import key
from hackagent.interfaces.tui.views.results.export import ResultsExportMixin
from hackagent.interfaces.results import (
    MAX_GOALS,
    attack_line,
    audit_lines,
    campaign_line,
    count,
    goal_line,
    more_line,
    newest_first,
    read_outline,
    read_results,
    reply_lines,
    runs_of,
)


@dataclass(frozen=True)
class _Store:
    """A place runs may have been recorded, and what to call it on screen."""

    label: str
    open: Callable[[], Any]


class ResultsTab(ResultsExportMixin, BaseTab):
    """Campaigns, their attacks, and the goals each attack tried."""

    DEFAULT_CSS = """
    ResultsTab { layout: vertical; }
    ResultsTab #results-tree { height: 1fr; padding: 1 1 0 1; }
    ResultsTab #results-empty {
        dock: top; margin: 1 1 0 1; color: $text-muted; display: none;
    }
    """

    BINDINGS = [
        key("refresh"),
        key("switch_store"),
        key("export_csv"),
        key("export_json"),
    ]

    def __init__(self, cli_config: CLIConfig, **kwargs: Any) -> None:
        super().__init__(cli_config, **kwargs)
        self.results_data: list[Any] = []
        self._campaigns: list[Any] = []
        self._agent_map: dict[str, str] = {}
        self._attack_map: dict[str, str] = {}
        #: ``(jailbroken, mitigated, recorded)`` of each attack run whose
        #: results were read; a run missing here is still being counted.
        self._result_counts: dict[str, tuple] = {}
        #: Where the runs on screen come from, as the title bar says it.
        self.said = ""
        self._results_of_run: dict[str, list[Any]] = {}
        #: The store on screen. Set by every refresh, and by the switch key,
        #: which is what makes it a choice rather than a guess.
        self._store_label: Optional[str] = None
        #: True once the user picked a store, after which the view stays
        #: there — an empty account they asked for is an answer.
        self._store_chosen = False
        #: Which read is current: a read started before the last refresh
        #: or switch draws nothing.
        self._generation = 0
        #: The tree's node of each attack run, and of each campaign with
        #: its runs, to relabel as counts arrive.
        self._run_nodes: dict[str, TreeNode[Any]] = {}
        self._campaign_nodes: dict[str, tuple[TreeNode[Any], Any, list[Any]]] = {}

    def compose(self) -> ComposeResult:
        tree: Tree[Any] = Tree("runs", id="results-tree")
        tree.show_root = False
        tree.guide_depth = 2
        yield tree
        yield Static(
            "No campaign recorded here yet: run one from the builder, or press s "
            "to read the other store.",
            id="results-empty",
        )

    # -- loading -------------------------------------------------------------

    def _stores(self) -> list["_Store"]:
        """The stores that may hold runs, in the order they are tried.

        Offer the account only when the session selects remote storage.
        The local database is always available as a separate source.
        """
        stores = []
        settings = getattr(self.cli_config, "settings", None)
        if isinstance(settings, Settings) and settings.mode is Mode.REMOTE:
            stores.append(_Store("the account", self.client))
        stores.append(_Store("this machine", self.local_client))
        return stores

    def refresh_data(self) -> None:
        """Read the store the user chose, or find one worth showing.

        Until a store is chosen, this looks for one with runs in it: an
        account that cannot be reached, or that has nothing, is no reason to
        show an empty screen while this machine holds what was just run.
        Once ``s`` has chosen one, that is the one read, empty or not.

        The reading happens on a thread of its own (:meth:`_load`): what is
        on screen stays until there is something to replace it.
        """
        stores = self._stores()
        if self._store_chosen:
            # Asked for by name: showing a different store instead would be
            # the very guessing the key exists to undo.
            stores = [
                store for store in stores if store.label == self._store_label
            ] or stores[:1]
        self._generation += 1
        generation = self._generation
        self._say(paint("reading…", SECONDARY))
        self.run_worker(
            lambda: self._load(generation, stores),
            thread=True,
            exclusive=True,
            group="results-read",
        )

    def _current(self, generation: int) -> bool:
        return generation == self._generation and self.is_attached

    def _load(self, generation: int, stores: list["_Store"]) -> None:
        """Read the stores in turn, on the worker's thread: the outline of
        the first with campaigns, then its results run by run."""
        problems: list[tuple[str, str]] = []
        empty: Optional[tuple["_Store", dict[str, Any]]] = None
        for store in stores:
            try:
                session = store.open()
                loaded = self._read(session)
            except Exception as exc:
                problems.append((store.label, str(exc)))
                continue
            if loaded["campaigns"]:
                self._from_thread(
                    self._outlined, generation, loaded, store.label, problems
                )
                self._count(generation, session, loaded)
                return
            empty = empty or (store, loaded)
        if empty is not None:
            self._from_thread(
                self._outlined, generation, empty[1], empty[0].label, problems
            )
            return
        self._from_thread(self._unreadable, generation, problems, stores)

    def _from_thread(self, callback: Callable[..., Any], *args: Any) -> None:
        """Run ``callback`` on the app's thread, unless the app has gone."""
        try:
            self.app.call_from_thread(callback, *args)
        except Exception:  # the view closed while reading: nothing to draw
            pass

    def _outlined(
        self,
        generation: int,
        loaded: dict[str, Any],
        source: str,
        problems: Sequence[tuple[str, str]],
    ) -> None:
        if not self._current(generation):
            return
        self._apply(loaded)
        self._show(source, problems)

    def _unreadable(
        self,
        generation: int,
        problems: Sequence[tuple[str, str]],
        stores: Sequence["_Store"],
    ) -> None:
        if not self._current(generation):
            return
        # Whatever was on screen came from a store that is not being shown
        # any more; leaving it there would credit those runs to this one.
        self._clear()
        said = "; ".join(f"{label}: {message}" for label, message in problems)
        self._store_label = stores[0].label if stores else None
        switch = self._switch_hint(problems)
        self._say(
            f"[$error]could not read results: {escape(said)}[/]"
            + (f" · {switch}" if switch else "")
        )

    def _count(self, generation: int, session: Any, loaded: dict[str, Any]) -> None:
        """Read each attack run's results, newest campaign first, and hand
        them to the view one run at a time."""
        recency = {
            str(campaign.id): str(getattr(campaign, "created_at", ""))
            for campaign in loaded["campaigns"]
        }
        runs = sorted(
            loaded["runs"],
            key=lambda run: recency.get(str(getattr(run, "campaign_run_id", "")), ""),
            reverse=True,
        )
        for run in runs:
            if generation != self._generation:
                return
            items = read_results(session, run)
            self._from_thread(self._counted, generation, str(run.id), items)

    def _counted(self, generation: int, run_id: str, items: list[Any]) -> None:
        """One attack run's results arrived: count them, relabel its line
        and its campaign's, and list its goals if it is open."""
        if not self._current(generation):
            return
        self._results_of_run[run_id] = items
        self._result_counts[run_id] = count(items)
        node = self._run_nodes.get(run_id)
        if node is None:
            return
        run = node.data[1]
        node.set_label(self._attack_label(run))
        if node.is_expanded:
            self._list_goals(node)
        campaign_id = str(getattr(run, "campaign_run_id", "") or "")
        if campaign_id in self._campaign_nodes:
            parent, campaign, runs = self._campaign_nodes[campaign_id]
            parent.set_label(self._campaign_label(campaign, runs))

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
        return f"s: {escape(others[0])}{unread}"

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
        """The outline of one store, or an exception: nothing is assigned
        until the whole read succeeds, so a store that fails halfway cannot
        leave half of its runs on screen. The results are read after, by
        :meth:`_count`."""
        return read_outline(session)

    def _clear(self) -> None:
        """Show nothing: no store answered, so nothing can be attributed."""
        self._apply(
            {
                "campaigns": [],
                "runs": [],
                "attacks": {},
                "agents": {},
            }
        )
        self.query_one("#results-tree", Tree).clear()

    def _apply(self, loaded: dict[str, Any]) -> None:
        self._campaigns = loaded["campaigns"]
        self.results_data = loaded["runs"]
        self._attack_map = loaded["attacks"]
        self._agent_map = loaded["agents"]
        self._result_counts = {}
        self._results_of_run = {}

    # -- the tree ------------------------------------------------------------

    def _build_tree(
        self, source: str = "", problems: Sequence[tuple[str, str]] = ()
    ) -> None:
        tree = self.query_one("#results-tree", Tree)
        tree.clear()
        self._run_nodes.clear()
        self._campaign_nodes.clear()
        campaigns = newest_first(self._campaigns)
        self.query_one("#results-empty", Static).display = not campaigns
        for campaign in campaigns:
            runs = runs_of(self.results_data, campaign)
            node = tree.root.add(self._campaign_label(campaign, runs), expand=False)
            self._campaign_nodes[str(campaign.id)] = (node, campaign, runs)
            self._add_audit(node, getattr(campaign, "audit", None))
            for run in runs:
                self._add_attack(node, run)
        # Which store this is, and that there is another one, are part of
        # reading the list: runs recorded in an account that is down would
        # otherwise look as though they never happened.
        said = [
            f"{len(campaigns)} {'campaign' if len(campaigns) == 1 else 'campaigns'}"
        ]
        if source:
            said.append(escape(source))
        if switch := self._switch_hint(problems):
            said.append(switch)
        self._say(" · ".join(said))

    def _say(self, markup: str) -> None:
        """Say where the runs come from, in the screen's title bar."""
        self.said = markup
        bar = title_bar(self)
        if bar is not None:
            bar.show(context=markup)

    def _campaign_label(self, campaign: Any, runs: list[Any]) -> str:
        return campaign_line(campaign, runs, self._result_counts, self._agent_map)

    def _add_audit(self, parent: TreeNode[Any], audit: Any) -> None:
        """The judge audit qualifies every attack of the campaign, so it sits first."""
        said = audit_lines(audit)
        if said is None:
            return
        line, table = said
        node = parent.add(line)
        for row in table:
            node.add_leaf(row)

    def _attack_label(self, run: Any) -> str:
        return attack_line(run, self._result_counts, self._attack_map)

    def _add_attack(self, parent: TreeNode[Any], run: Any) -> None:
        """The attack's line; its goals are listed when it is opened."""
        node = parent.add(
            self._attack_label(run),
            data=("run", run),
            expand=False,
            allow_expand=True,
        )
        self._run_nodes[str(run.id)] = node

    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        data = event.node.data
        if isinstance(data, tuple) and data and data[0] == "run":
            self._list_goals(event.node)

    def _list_goals(self, node: TreeNode[Any]) -> None:
        """The goals an attack tried, under its line, once its results are
        read; until then, that they are being read."""
        run = node.data[1]
        results = self._results_of_run.get(str(run.id))
        node.remove_children()
        if results is None:
            node.add_leaf(paint("reading its goals…", SECONDARY))
            return
        if not results:
            node.add_leaf(paint("no goals recorded", SECONDARY))
            return
        for result in results[:MAX_GOALS]:
            goal = node.add(goal_line(result), expand=False)
            for line in reply_lines(result):
                goal.add_leaf(line)
        if more := more_line(MAX_GOALS, len(results)):
            node.add_leaf(more)

    # -- keys ----------------------------------------------------------------

    def action_refresh(self) -> None:
        self.refresh_data()

    def action_export_csv(self) -> None:
        self._export_results_csv()

    def action_export_json(self) -> None:
        self._export_results_json()


__all__ = ["ResultsTab"]
