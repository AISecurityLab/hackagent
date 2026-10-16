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
from textual.containers import Center, Vertical, VerticalScroll
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


#: Where the welcome screen can send you. A choice earns a button only by
#: landing somewhere the others do not.
BUILD, EXAMPLE, OPEN, RESULTS = "build", "example", "open", "results"


class WelcomeScreen(Screen[str]):
    """The logo and the ways in. Dismisses with the chosen destination."""

    DEFAULT_CSS = """
    /* The screen itself must not scroll: focusing a button would scroll it
       into view and carry the logo off the top. Only #choices scrolls. */
    WelcomeScreen {
        align-horizontal: center; padding-top: 1; overflow: hidden;
    }
    /* max-width keeps the card inside a terminal narrower than it wants to
       be, so its text wraps rather than being cut off at the edge. */
    WelcomeScreen #card {
        width: 84; max-width: 100%; height: auto; max-height: 100%; padding: 0 2;
    }
    /* Only the choices scroll. The logo stays put: on a short terminal the
       alternative is a welcome screen with no logo on it, and a button you
       cannot see is a button that does not exist. */
    WelcomeScreen #choices {
        width: 84; max-width: 100%; height: 1fr; overflow-y: auto; padding: 0 2;
    }
    /* The logo is line art: `width: auto` sizes the widget to it so `Center`
       can centre the block. Centring the text instead would centre each line
       on its own and shear the letters apart. */
    WelcomeScreen #logo { color: $brand; text-style: bold; width: auto; height: auto; }
    WelcomeScreen #tagline {
        color: $text-muted; width: 100%; text-align: center; margin-bottom: 1;
    }
    WelcomeScreen .choice { width: 100%; }
    /* Textual marks a focused button with `bold reverse`, which inverts it to
       black on white and makes it read as a different kind of button. Four
       ways in of equal standing: keep the colour, show focus with weight and
       a tint. */
    WelcomeScreen .choice:focus {
        text-style: bold;
        background-tint: $foreground 20%;
    }
    WelcomeScreen #aside { color: $text-muted; width: 100%; text-align: center; }
    """

    BINDINGS = [
        Binding("escape", "choose('build')", "Build a campaign", show=False),
        Binding("q", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="card"):
            with Center():
                yield Static(LOGO, id="logo")
            yield Static(TAGLINE, id="tagline")
        with VerticalScroll(id="choices"):
            for label, destination in (
                ("Build your own campaign", BUILD),
                ("Start from an example", EXAMPLE),
                ("Open a campaign file", OPEN),
                ("Show results", RESULTS),
            ):
                yield Button(label, id=destination, variant="success", classes="choice")
            yield Static(
                "Every example is a campaign you can read and edit before it runs.",
                id="aside",
            )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(f"#{BUILD}", Button).focus()

    def action_choose(self, destination: str) -> None:
        self.dismiss(destination)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(str(event.button.id or BUILD))


__all__ = [
    "BUILD",
    "EXAMPLE",
    "LOGO",
    "OPEN",
    "RESULTS",
    "Template",
    "WelcomeScreen",
    "starting_point",
]
