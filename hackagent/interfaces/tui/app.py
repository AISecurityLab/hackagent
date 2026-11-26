# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Main TUI Application

One screen, one job: build a campaign, check it, run it.

The app opens on :class:`WelcomeScreen` — the logo, and the ways in — then
hands over to :class:`CampaignBuilder`; past runs open on a screen of their
own.
"""

import os
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.widgets import Footer

from hackagent.interfaces.tui.keys import key
from hackagent.interfaces.cli.config import CLIConfig
from hackagent.interfaces.tui.theme import css_variables
from hackagent.interfaces.tui.views.agents import AgentsTab
from hackagent.interfaces.tui.views.campaign import CampaignBuilder
from hackagent.interfaces.tui.views.config import ConfigTab
from hackagent.interfaces.tui.views.results import ResultsTab


def _start_multiprocessing_tracker() -> None:
    """Start multiprocessing's resource tracker while stderr is still a file.

    Textual replaces ``sys.stderr`` with an object that has no file
    descriptor. The first multiprocessing lock made after that starts the
    tracker, which hands its child stderr's descriptor and fails with
    "bad value(s) in fds_to_keep". tqdm makes such a lock whenever
    ``datasets`` loads a Hugging Face dataset, so a campaign whose goals come
    from a preset could not run in the TUI. Started here, the tracker is
    already running when that lock is made.
    """
    if os.name != "posix":  # Windows has no resource tracker.
        return
    from multiprocessing import resource_tracker

    try:
        resource_tracker.ensure_running()
    except Exception:  # noqa: BLE001 - never stop the TUI from opening over it
        pass


#: What a screen is for, said on its help (F1). The main screen is the
#: builder.
_ABOUT = {
    "Screen": (
        "Build a campaign, check it, run it. Every field starts at its "
        "default, shown dimmed; problems appear on the field they concern, "
        "and Run stays disabled until there are none."
    ),
    "RunScreen": "The run's log, as it happens. Leaving does not stop the run.",
    "ResultsScreen": "Every campaign recorded, its attacks, and each goal's verdict.",
    "ExampleScreen": "The example campaigns, by folder. One opens in the builder.",
    "WelcomeScreen": "The ways in: build a campaign, start from an example, open one.",
}


class HackAgentTUI(App):
    """HackAgent Terminal User Interface Application"""

    #: Textual's command palette is not one of HackAgent's keys.
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    Screen { background: $surface; }
    Footer { background: $brand-darker; color: $brand-text; }
    /* Every screen's content in one box, with the same space between it
       and the title bar above as between it and the footer below. */
    .frame-body {
        height: 1fr; margin: 1 1; border: round $primary; background: $surface;
    }
    /* Inside it, a list, a tree or a log needs no box of its own. */
    .frame-body OptionList, .frame-body OptionList:focus,
    .frame-body Tree, .frame-body Tree:focus,
    .frame-body RichLog, .frame-body RichLog:focus {
        border: none; background-tint: $foreground 0%;
    }
    * { scrollbar-size-vertical: 1; }
    """

    TITLE = "HackAgent"
    SUB_TITLE = "Build a campaign, check it, run it"
    VIEWS = ("campaign", "results", "agents", "config")

    BINDINGS = [
        # Not a priority binding: a text field must be able to receive 'q'.
        key("quit"),
        key("help"),
        key("copy", "copy_selection", show=False),
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
            initial_tab: The view to open, defaulting to the campaign builder.
            initial_data: A campaign to open in the builder instead of the
                welcome screen (``campaign_path`` or ``campaign_yaml``).
        """
        super().__init__()
        self.cli_config = cli_config
        self.view = initial_tab if initial_tab in self.VIEWS else "campaign"
        self.initial_tab = self.view
        self.initial_data = initial_data or {}
        self.dark = True

    def get_css_variables(self) -> dict[str, str]:
        """Expose the HackAgent brand palette as CSS variables."""
        return {**super().get_css_variables(), **css_variables()}

    def run(self, *args: Any, **kwargs: Any) -> Any:
        _start_multiprocessing_tracker()
        return super().run(*args, **kwargs)

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
        """Show every key of the screen on top, and what each one does."""
        from hackagent.interfaces.tui.keys import known
        from hackagent.interfaces.tui.views.campaign.screens import HelpScreen

        if isinstance(self.screen, HelpScreen):
            return
        rows: dict[str, tuple[str, str]] = {}
        for active in self.screen.active_bindings.values():
            item = known(active.binding)
            if item is not None and item.word not in rows:
                shown = item.display or self.get_key_display(active.binding)
                rows[item.word] = (shown, item.does)
        about = _ABOUT.get(type(self.screen).__name__, "")
        self.push_screen(HelpScreen(list(rows.values()), about))

    def action_refresh(self) -> None:
        """Refresh whatever view is on screen."""
        try:
            for descendant in self.screen.query("*"):
                if hasattr(descendant, "refresh_data"):
                    descendant.refresh_data()
                    return
        except Exception:
            pass

    def _run_log_text(self) -> str:
        """The campaign run's log as plain text, as the run view shows it;
        empty before any run."""
        from rich.text import Text

        builder = self.query(CampaignBuilder)
        if not builder:
            return ""
        return "\n".join(
            Text.from_markup(line).plain for line in builder.first()._run_lines
        )

    def action_copy_selection(self) -> None:
        """Copy a text selection, else the run's log, to the clipboard — bound
        to Ctrl+Y.

        If you've dragged to select text, that selection is copied. Otherwise
        it copies the campaign run's log, so you can copy without needing the
        mouse at all. Uses Textual's terminal-native clipboard (OSC 52), which
        works locally and over SSH.
        """
        from hackagent.interfaces.tui.widgets.clipboard import copy_to_clipboard

        source = "selection"
        text = ""
        try:
            text = self.screen.get_selected_text() or ""
        except Exception:
            text = ""
        if not text:
            text, source = self._run_log_text(), "the run's log"
        if not text:
            self.notify(
                "Nothing to copy yet — run a campaign, or drag to select text first.",
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
        """Show a warning, marked ``!`` as the CLI marks one."""
        self.notify(f"! {message}", title="Warning", severity="warning")

    def show_info(self, message: str) -> None:
        """Show a message in passing, unmarked as the CLI says one."""
        self.notify(message, title="Info", severity="information")
