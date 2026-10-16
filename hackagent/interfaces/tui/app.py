# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Main TUI Application

One screen, one job: build a campaign, check it, run it.

The app opens on :class:`WelcomeScreen` — the logo, and a working campaign to
start from — then hands over to :class:`CampaignBuilder`. The other views
(results, targets, config) are no longer part of this app; they are still
reachable on their own, which is what ``hackagent results`` and
``hackagent agent`` open.
"""

from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, TabbedContent

from hackagent.interfaces.cli.config import CLIConfig
from hackagent.interfaces.tui.theme import css_variables
from hackagent.interfaces.tui.views.agents import AgentsTab
from hackagent.interfaces.tui.views.campaign import CampaignBuilder
from hackagent.interfaces.tui.views.config import ConfigTab
from hackagent.interfaces.tui.views.results import ResultsTab


class HackAgentTUI(App):
    """HackAgent Terminal User Interface Application"""

    CSS = """
    Screen {
        background: $surface;
    }

    Footer {
        background: $brand-darker;  /* darker red */
        color: $brand-text;
    }

    TabbedContent {
        height: 100%;
        border: solid $brand;  /* red - HackAgent brand color */
    }

    TabPane {
        padding: 1 2;
        height: 100%;
    }

    TabbedContent > ContentSwitcher {
        height: 1fr;
    }

    TabbedContent > ContentSwitcher > * > * {
        background: $surface;
    }

    Tabs {
        background: $brand-darker;
    }

    Tab {
        color: $brand-text-muted;
        background: $brand-darker;
    }

    Tab.-active {
        color: $brand-text;
        background: $brand;  /* brighter red when active — clear contrast */
        text-style: bold underline;
    }

    Tab:hover {
        background: $brand-hover;
    }

    .title-bar {
        dock: top;
        width: 100%;
        background: $brand-dark;
        color: $brand-text;
        height: 3;
        content-align: center middle;
    }

    .section {
        border: solid $brand;
        padding: 1;
        margin: 1;
        height: auto;
    }

    .info-box {
        background: $panel;
        border: solid $brand;
        padding: 1;
        margin: 1;
    }

    Button {
        margin: 1;
    }

    Button.-primary {
        background: $brand-dark;
        color: $brand-text;
    }

    Button.-primary:hover {
        background: $brand;
    }

    DataTable {
        height: 100%;
    }

    DataTable > .datatable--header {
        background: $brand-dark;
        color: $brand-text;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        background: $brand-hover;
    }

    /* Results tab specific styles - horizontal split 20-80 */
    ResultsTab #results-left-panel {
        border-right: solid $brand;
        background: $panel;
    }

    ResultsTab #results-right-panel {
        background: $panel;
    }

    ResultsTab #results-title {
        height: 3;
        width: 100%;
        text-align: center;
        background: $brand-dark;
        color: $brand-text;
        padding: 1;
    }

    ResultsTab #details-title {
        height: 3;
        width: 100%;
        text-align: center;
        background: $brand-dark;
        color: $brand-text;
        padding: 1;
    }

    ResultsTab .toolbar {
        height: 3;
        width: 100%;
        padding: 0 1;
    }
    """

    TITLE = "HackAgent"
    SUB_TITLE = "Build a campaign, check it, run it"

    #: The view this app shows. ``campaign`` is the app proper; the others
    #: exist so ``hackagent results`` and ``hackagent agent`` keep working.
    VIEWS = ("campaign", "results", "agents", "config")

    BINDINGS = [
        # Not a priority binding: a text field must be able to receive 'q'.
        Binding("q", "quit", "Quit"),
        Binding("f1", "help", "Help"),
        Binding("f5", "refresh", "Refresh", show=False),
        Binding("ctrl+y", "copy_selection", "Copy logs", show=False),
    ]

    def __init__(
        self,
        cli_config: CLIConfig,
        initial_tab: str = "campaign",
        initial_data: dict[Any, Any] | None = None,
    ):
        """Initialize the TUI application.

        Args:
            cli_config: CLI configuration object
            initial_tab: Which view to show. Defaults to the campaign builder;
                the legacy names ``results``, ``agents`` and ``config`` open
                that view on its own.
            initial_data: Data to pre-fill the view with (default: None)
        """
        super().__init__()
        self.cli_config = cli_config
        self.view = initial_tab if initial_tab in self.VIEWS else "campaign"
        self.initial_tab = self.view
        self.initial_data = initial_data or {}
        self.dark = True  # Use dark theme by default

    def get_css_variables(self) -> dict[str, str]:
        """Expose the HackAgent brand palette as CSS variables."""
        return {**super().get_css_variables(), **css_variables()}

    def compose(self) -> ComposeResult:
        """One view and a footer.

        No header bar: the view below says what it is — the builder opens on
        the campaign's name and whether it is ready to run — so a title strip
        above it only costs rows the form can use.
        """
        if self.view == "results":
            yield ResultsTab(self.cli_config)
        elif self.view == "agents":
            yield AgentsTab(self.cli_config)
        elif self.view == "config":
            yield ConfigTab(self.cli_config)
        else:
            yield CampaignBuilder(self.cli_config, initial_data=self.initial_data)
        yield Footer()

    def on_mount(self) -> None:
        """Open on the welcome screen, unless a campaign was handed to us."""
        self.title = self.TITLE
        self.sub_title = self.SUB_TITLE
        if self.view != "campaign":
            return
        if self.initial_data.get("campaign_path") or self.initial_data.get(
            "campaign_yaml"
        ):
            return
        self.show_welcome()

    def show_welcome(self) -> None:
        """Offer the ways in, and take the one chosen."""
        from hackagent.interfaces.tui.views.campaign.welcome import (
            BUILD,
            EXAMPLE,
            OPEN,
            RESULTS,
            WelcomeScreen,
            starting_point,
        )

        def _chose(destination: str | None) -> None:
            builder = self.query_one(CampaignBuilder)
            if destination == EXAMPLE:
                self._pick_example()
            elif destination == OPEN:
                self._open_campaign()
            elif destination == RESULTS:
                self._show_results()
            elif destination == BUILD or destination is None:
                builder.start_from(starting_point())

        self.push_screen(WelcomeScreen(), _chose)

    def _open_campaign(self) -> None:
        """Ask for a path and open it.

        Not the builder's own Open, which first asks whether to discard the
        draft: arriving from the welcome screen there is nothing to discard.
        """
        from hackagent.interfaces.tui.views.campaign.screens import PathScreen

        def _chosen(value: Any) -> None:
            if not value:
                self.show_welcome()
                return
            self.query_one(CampaignBuilder).open_path(Path(value).expanduser())

        self.push_screen(PathScreen("Open campaign", "campaign.yaml", "Open"), _chosen)

    def _pick_example(self) -> None:
        """Open one of the shipped examples in the builder, ready to read."""
        from hackagent import examples as examples_catalog
        from hackagent.interfaces.tui.views.campaign.screens import ExampleScreen

        found = examples_catalog.campaign_files()
        if not found:
            self.notify(
                "No examples found beside this install.",
                title="Nothing to start from",
                severity="warning",
            )
            self.show_welcome()
            return

        def _chosen(path: Any) -> None:
            if path is None:
                self.show_welcome()
                return
            # Read as a file, so the campaign keeps the comments explaining it.
            self.query_one(CampaignBuilder).open_path(path)

        self.push_screen(ExampleScreen(found), _chosen)

    def _show_results(self) -> None:
        """Past runs, then back to the ways in."""
        from hackagent.interfaces.tui.views.campaign.screens import ResultsScreen

        self.push_screen(ResultsScreen(self.cli_config), lambda _: self.show_welcome())

    def action_help(self) -> None:
        """Show the keys and what this screen is for."""
        builder = self.query(CampaignBuilder)
        if builder:
            builder.first().action_help()

    def action_refresh(self) -> None:
        """Refresh whatever view is on screen."""
        try:
            for descendant in self.screen.query("*"):
                if hasattr(descendant, "refresh_data"):
                    descendant.refresh_data()
                    return
        except Exception:
            pass

    def _active_monitor_text(self) -> tuple[str, str]:
        """Return ``(text, source)`` for the active attack-monitor panel.

        Picks the Actions panel when its tab is active, otherwise the Logs
        panel. Returns ``("", "logs")`` when no viewer is present.
        """
        from hackagent.interfaces.tui.widgets.actions import AgentActionsViewer
        from hackagent.interfaces.tui.widgets.logs import AttackLogViewer

        active = None
        try:
            monitor = self.query_one("#attack-monitor-container")
            active = monitor.query_one(TabbedContent).active
        except Exception:
            active = None

        if active == "actions-tab":
            try:
                return self.query_one(AgentActionsViewer).get_actions_text(), "actions"
            except Exception:
                pass
        try:
            return self.query_one(AttackLogViewer).get_log_text(), "logs"
        except Exception:
            pass
        try:
            return self.query_one(AgentActionsViewer).get_actions_text(), "actions"
        except Exception:
            return "", "logs"

    def action_copy_selection(self) -> None:
        """Copy logs (or a text selection) to the clipboard — bound to Ctrl+Y.

        If you've dragged to select text, that selection is copied. Otherwise it
        copies the whole visible Logs (or Actions) panel — so you can copy
        without needing the mouse at all. Uses Textual's terminal-native
        clipboard (OSC 52), which works locally and over SSH.
        """
        from hackagent.interfaces.tui.widgets.clipboard import copy_to_clipboard

        source = "selection"
        text = ""
        try:
            text = self.screen.get_selected_text() or ""
        except Exception:
            text = ""
        if not text:
            text, source = self._active_monitor_text()
        if not text:
            self.notify(
                "Nothing to copy yet — run an attack, or drag to select text first.",
                title="Copy",
                severity="warning",
            )
            return
        copy_to_clipboard(self, text)
        self.notify(
            f"Copied {source} ({len(text)} characters) to the clipboard.",
            title="Copy",
        )

    def show_success(self, message: str) -> None:
        """Show success notification with checkmark."""
        self.notify(f"✓ {message}", title="Success", severity="information")

    def show_error(self, message: str) -> None:
        """Show error notification with X mark."""
        self.notify(f"✗ {message}", title="Error", severity="error")

    def show_warning(self, message: str) -> None:
        """Show warning notification with warning sign."""
        self.notify(f"⚠ {message}", title="Warning", severity="warning")

    def show_info(self, message: str) -> None:
        """Show info notification with info icon."""
        self.notify(f"ℹ {message}", title="Info", severity="information")
