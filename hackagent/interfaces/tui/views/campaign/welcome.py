# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The screen HackAgent opens on: what this is, and one way in.

There is a single action, because there is a single thing to do here. The
campaign it hands over is complete and runnable, so the builder opens on
something worth reading rather than an empty form.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from hackagent.interfaces.cli.banner import HACKAGENT_BANNER

TAGLINE = "Red-team an AI model with a campaign you can save, share and re-run."

#: The logo, without the blank lines the constant is written with. There is
#: one banner and the welcome screen always shows it: a terminal too narrow
#: for it gets less of it, never a substitute for it.
LOGO = HACKAGENT_BANNER.strip("\n")

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


class WelcomeScreen(Screen[bool]):
    """Shows the logo and starts the builder. Dismisses with ``True``."""

    DEFAULT_CSS = """
    WelcomeScreen { align: center middle; }
    /* max-width keeps the card inside a terminal narrower than it wants to
       be, so its text wraps rather than being cut off at the edge. */
    WelcomeScreen #card { width: 84; max-width: 100%; height: auto; padding: 1 2; }
    /* The logo is line art: `width: auto` sizes the widget to it so `Center`
       can centre the block. Centring the text instead would centre each line
       on its own and shear the letters apart. */
    WelcomeScreen #logo { color: $brand; text-style: bold; width: auto; height: auto; }
    WelcomeScreen #tagline {
        color: $text-muted; width: 100%; text-align: center; margin: 1 0;
    }
    WelcomeScreen #start { width: 100%; margin-bottom: 1; }
    WelcomeScreen #aside { color: $text-muted; width: 100%; text-align: center; }
    """

    BINDINGS = [
        Binding("enter", "start", "Build a campaign", show=False),
        Binding("escape", "start", "Build a campaign", show=False),
        Binding("q", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="card"):
            with Center():
                yield Static(LOGO, id="logo")
            yield Static(TAGLINE, id="tagline")
            yield Button("Build your own campaign", id="start", variant="success")
            yield Static(
                "Already have one? Open it from the builder with ctrl+O.",
                id="aside",
            )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#start", Button).focus()

    def action_start(self) -> None:
        self.dismiss(True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(True)


__all__ = ["LOGO", "Template", "WelcomeScreen", "starting_point"]
