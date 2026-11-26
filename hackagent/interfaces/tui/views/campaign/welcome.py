# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The screen HackAgent opens on: what this is, and what it can do.

One menu, one entry per thing to do, each landing somewhere the others do
not: a campaign (new, from an example, or from a file: one entry, since all
three open the builder), past results, the dataset presets, the setup, the
web dashboard. What the command line can do, the app offers here.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Footer, OptionList, Static
from textual.widgets.option_list import Option

from hackagent.interfaces.brand import BANNER, TAGLINE
from hackagent.interfaces.palette import SECONDARY
from hackagent.interfaces.tui.keys import key

#: There is one logo and the welcome screen always shows it: a terminal too
#: narrow for it gets less of it, never a substitute for it.
LOGO = BANNER

_LOCAL_MODEL: dict[str, Any] = {
    "name": "local-model",
    "connection": {
        "provider": "local",
        "type": "OPENAI_SDK",
        "endpoint": "http://127.0.0.1:8000/v1",
    },
}


@dataclass(frozen=True)
class Template:
    """A campaign to start from."""

    title: str
    document: dict[str, Any]
    #: Set when the campaign came from a file, so saving goes back to it.
    path: Optional[Any] = None


def starting_point() -> Template:
    """The campaign the builder opens on.

    Every part is filled in and valid — a dataset, a target, one plain attack
    and a judge — so the first screen can be read, edited and run as it is.
    """
    return Template(
        "Your campaign",
        {
            "version": 1,
            "campaign": {"name": "My campaign"},
            "dataset": {
                "source": {"type": "preset", "name": "harmbench"},
                "selection": {"limit": 10},
            },
            "target": copy.deepcopy(_LOCAL_MODEL),
            "attacks": [{"name": "baseline"}],
            "evaluation": {
                "judges": [
                    {**copy.deepcopy(_LOCAL_MODEL), "scoring": {"type": "harmbench"}}
                ]
            },
        },
    )


#: Where the welcome screen can send you. An entry earns its place only by
#: landing somewhere the others do not. The campaign entry opens its own
#: menu in place (:data:`STARTS`), which answers with one of the first three.
BUILD, EXAMPLE, OPEN = "build", "example", "open"
CAMPAIGN, RESULTS, DATASETS, QUEUED, DASHBOARD, SETTINGS = (
    "campaign",
    "results",
    "datasets",
    "queued",
    "dashboard",
    "settings",
)

#: The menu: each entry, and what it is for; the command line's command for
#: the same thing is in brackets in the help (F1).
MENU: tuple[tuple[str, str, str], ...] = (
    (CAMPAIGN, "Campaign", "New, from an example, or from a file"),
    (RESULTS, "Results", "What past runs found"),
    (DATASETS, "Datasets", "Browse the presets and sample their goals"),
    (QUEUED, "Queued runs", "Run one queued from the dashboard"),
    (DASHBOARD, "Dashboard", "Serve the web dashboard and open it"),
    (SETTINGS, "Settings", "Where results are kept, and what is missing"),
)


#: Where a campaign can start from, for the builder to open: the campaign
#: entry's own menu.
STARTS: tuple[tuple[str, str, str], ...] = (
    (BUILD, "New", "A complete campaign, ready to edit and run"),
    (EXAMPLE, "From an example", "The example campaigns, by folder"),
    (OPEN, "From a file", "A campaign.yaml of your own"),
)


def menu_entry(label: str, about: str) -> Text:
    """An entry: its name, bold, then what it is for."""
    return Text.assemble((f"{label:<17}", "bold"), (about, SECONDARY))


class WelcomeScreen(Screen[str]):
    """The logo and the menu. Dismisses with the chosen destination.

    The campaign entry opens its menu in the same place, under the same
    logo, titled; back returns to the first menu on the entry it left.
    """

    DEFAULT_CSS = """
    /* The screen itself must not scroll: only the menu does, so the logo
       always stays on top. */
    WelcomeScreen {
        align-horizontal: center; padding-top: 1; overflow: hidden;
    }
    /* max-width keeps the card inside a terminal narrower than it wants to
       be, so its text wraps rather than being cut off at the edge. */
    WelcomeScreen #card {
        width: 84; max-width: 100%; height: auto; max-height: 100%; padding: 0 2;
    }
    /* The logo is line art: `width: auto` sizes the widget to it so `Center`
       can centre the block. Centring the text instead would centre each line
       on its own and shear the letters apart. */
    WelcomeScreen #logo { color: $brand; text-style: bold; width: auto; height: auto; }
    WelcomeScreen #tagline {
        color: $text-muted; width: 100%; text-align: center; margin-bottom: 1;
    }
    WelcomeScreen #menu {
        width: 64; max-width: 100%; height: auto; max-height: 1fr;
        border: round $primary; padding: 0 1;
    }
    WelcomeScreen #menu:focus { border: round $accent; background-tint: $foreground 0%; }
    WelcomeScreen #menu {
        border-title-color: $accent; border-title-style: bold;
        border-subtitle-color: $text-muted;
    }
    """

    BINDINGS = [
        key("choose", "move('down')", priority=True),
        key("choose", "move('up')", show=False, priority=True, keys="up"),
        key("open", priority=True),
        key("back", "back", show=False),
        key("quit", "app.quit"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="card"):
            with Center():
                yield Static(LOGO, id="logo")
            yield Static(TAGLINE, id="tagline")
            with Center():
                yield OptionList(id="menu")
        yield Footer()

    def on_mount(self) -> None:
        #: The menu shown: the first one, or the campaign entry's.
        self._entries = MENU
        self._show(MENU)
        self.query_one(OptionList).focus()

    def _show(
        self, entries: tuple[tuple[str, str, str], ...], title: str = "", at: int = 0
    ) -> None:
        """Show a menu in place of the one there, ``at`` its entry."""
        menu = self.query_one(OptionList)
        menu.clear_options()
        served = getattr(self.app, "dashboard", None)
        menu.add_options(
            Option(
                menu_entry(
                    label,
                    f"Serving at {served.dashboard.url}"
                    if destination == DASHBOARD and served is not None
                    else about,
                ),
                id=destination,
            )
            for destination, label, about in entries
        )
        menu.border_title = title
        # The first menu's Esc is a shortcut, to a new campaign; this one's
        # goes back, which the menu says since the footer cannot.
        menu.border_subtitle = "esc back" if title else ""
        menu.highlighted = at
        self._entries = entries

    def action_back(self) -> None:
        """From the campaign menu, back to the first one; from the first,
        into the builder on a new campaign."""
        if self._entries is STARTS:
            self._show(MENU, at=[entry[0] for entry in MENU].index(CAMPAIGN))
        else:
            self.dismiss(BUILD)

    def action_move(self, direction: str) -> None:
        """Move to the next or the previous entry."""
        menu = self.query_one(OptionList)
        menu.action_cursor_down() if direction == "down" else menu.action_cursor_up()

    def action_open(self) -> None:
        """Open the highlighted entry."""
        self.query_one(OptionList).action_select()

    def action_choose(self, destination: str) -> None:
        self.dismiss(destination)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        if event.option.id == CAMPAIGN:
            self._show(STARTS, title="Campaign")
            return
        self.dismiss(str(event.option.id))


__all__ = [
    "BUILD",
    "CAMPAIGN",
    "DASHBOARD",
    "DATASETS",
    "EXAMPLE",
    "LOGO",
    "MENU",
    "OPEN",
    "QUEUED",
    "RESULTS",
    "SETTINGS",
    "STARTS",
    "Template",
    "WelcomeScreen",
    "starting_point",
]
