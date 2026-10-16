# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The screens the builder opens: the run view, and small dialogs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Input,
    Label,
    OptionList,
    ProgressBar,
    RichLog,
    Static,
)
from textual.widgets.option_list import Option

_DIALOG_CSS = """
{name} {{ align: center middle; background: $background 60%; }}
{name} > Vertical {{
    width: 64; height: auto; padding: 1 2;
    border: round $primary; background: $panel;
}}
{name} Horizontal {{ height: auto; margin-top: 1; }}
{name} Button {{ width: 1fr; margin: 0 1 0 0; }}
"""


class ExampleScreen(ModalScreen[Optional[Path]]):
    """Pick one of the shipped examples. Dismisses with its path, or None."""

    DEFAULT_CSS = """
    ExampleScreen { align: center middle; background: $background 60%; }
    ExampleScreen > Vertical {
        width: 92; max-width: 100%; height: auto; max-height: 80%;
        padding: 1 2; border: round $primary; background: $panel;
    }
    ExampleScreen OptionList { height: auto; max-height: 24; border: none; }
    ExampleScreen .hint { color: $text-muted; margin-top: 1; }
    """

    BINDINGS = [Binding("escape", "dismiss(None)", "Cancel")]

    def __init__(self, examples: Mapping[str, Path]) -> None:
        super().__init__()
        self._examples = dict(examples)

    def compose(self) -> ComposeResult:
        from hackagent import examples as examples_catalog

        with Vertical():
            yield Label("[b]Start from an example[/b]")
            options = [
                Option(
                    f"[cyan]{escape(name)}[/cyan]\n"
                    f"  [dim]{escape(examples_catalog.describe(path))}[/dim]",
                    id=name,
                )
                for name, path in self._examples.items()
            ]
            yield OptionList(*options)
            yield Static(
                "The campaign opens in the builder: read it, change the model, "
                "then run it.",
                classes="hint",
            )

    def on_mount(self) -> None:
        self.query_one(OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.dismiss(self._examples.get(str(event.option.id)))


class ResultsScreen(Screen[None]):
    """Past runs, on a screen of their own."""

    DEFAULT_CSS = """
    ResultsScreen { background: $surface; }
    ResultsScreen #results-hint {
        height: 1; padding: 0 1; color: $text-muted; background: $panel;
    }
    """

    BINDINGS = [Binding("escape", "close", "Back")]

    def __init__(self, cli_config: Any) -> None:
        super().__init__()
        self._cli_config = cli_config

    def compose(self) -> ComposeResult:
        from hackagent.interfaces.tui.views.results import ResultsTab

        yield ResultsTab(self._cli_config)
        yield Static("esc back", id="results-hint")

    def action_close(self) -> None:
        self.dismiss(None)


class RunScreen(Screen[None]):
    """A running campaign, with the whole terminal to show it.

    The builder owns the run and keeps every line it has produced; this
    screen renders them. Leaving does not stop anything — the run carries on
    and reopening replays what was missed.
    """

    DEFAULT_CSS = """
    RunScreen { background: $surface; }
    RunScreen #run-head { height: 1; padding: 0 1; background: $panel; }
    RunScreen #run-progress { margin: 1 2 0 2; }
    RunScreen #run-log {
        height: 1fr; margin: 1 2; border: round $primary-darken-2;
    }
    RunScreen #run-hint {
        height: 1; padding: 0 1; color: $text-muted; background: $panel;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Back"),
        Binding("f3", "stop", "Stop"),
    ]

    def __init__(
        self,
        title: str,
        lines: Sequence[str],
        progress: float,
        stop: Callable[[], None],
    ) -> None:
        super().__init__()
        self._title = title
        self._lines = list(lines)
        self._progress = progress
        self._stop = stop

    def compose(self) -> ComposeResult:
        yield Static(f"[b]{escape(self._title)}[/b]", id="run-head")
        yield ProgressBar(total=100, show_eta=False, id="run-progress")
        yield RichLog(markup=True, wrap=True, id="run-log")
        yield Static(
            "esc back to the campaign · f3 stop · the run carries on either way",
            id="run-hint",
        )

    def on_mount(self) -> None:
        log = self.query_one("#run-log", RichLog)
        for line in self._lines:
            log.write(line)
        self.set_progress(self._progress)

    def write(self, markup: str) -> None:
        self.query_one("#run-log", RichLog).write(markup)

    def set_progress(self, value: float) -> None:
        self.query_one("#run-progress", ProgressBar).update(progress=value)

    def action_close(self) -> None:
        self.dismiss(None)

    def action_stop(self) -> None:
        self._stop()


class PathScreen(ModalScreen[Optional[str]]):
    DEFAULT_CSS = _DIALOG_CSS.format(name="PathScreen")
    BINDINGS = [Binding("escape", "dismiss(None)", "Cancel")]

    def __init__(self, title: str, default: str, action: str) -> None:
        super().__init__()
        self.title_text = title
        self.default = default
        self.action_label = action

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self.title_text)
            yield Input(value=self.default, id="path")
            with Horizontal():
                yield Button("Cancel", id="cancel")
                yield Button(self.action_label, id="ok", variant="primary")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip() or None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        value = self.query_one(Input).value.strip()
        self.dismiss(value or None if event.button.id == "ok" else None)


class ConfirmScreen(ModalScreen[bool]):
    DEFAULT_CSS = _DIALOG_CSS.format(name="ConfirmScreen").replace(
        "$primary", "$warning"
    )
    BINDINGS = [Binding("escape", "dismiss(False)", "Cancel")]

    def __init__(self, question: str, detail: str, action: str) -> None:
        super().__init__()
        self.question = question
        self.detail = detail
        self.action_label = action

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"[b]{escape(self.question)}[/b]")
            yield Static(f"[dim]{escape(self.detail)}[/dim]")
            with Horizontal():
                yield Button("Cancel", id="cancel")
                yield Button(self.action_label, id="ok", variant="warning")

    def on_mount(self) -> None:
        self.query_one("#cancel", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "ok")


class HelpScreen(ModalScreen[None]):
    """What this screen is for, and every key that does something."""

    DEFAULT_CSS = _DIALOG_CSS.format(name="HelpScreen").replace(
        "width: 64;", "width: 72;"
    )
    BINDINGS = [
        Binding("escape", "dismiss(None)", "Close"),
        Binding("f1", "dismiss(None)", "Close", show=False),
        Binding("?", "dismiss(None)", "Close", show=False),
    ]

    SECTIONS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
        (
            "Moving around",
            (
                ("↑ ↓", "choose a part of the campaign"),
                ("Tab", "edit that part's fields"),
                ("Esc", "back to the outline"),
                ("Delete", "remove the selected attack or judge"),
            ),
        ),
        (
            "Editing",
            (
                ("type", "override a field; empty means the dimmed default"),
                ("ctrl+t", "reset the field under the cursor"),
                ("F4", "open the whole campaign in $EDITOR"),
            ),
        ),
        (
            "The campaign",
            (
                ("ctrl+s", "save to a file"),
                ("ctrl+o", "open a campaign file"),
                ("ctrl+r", "run it"),
            ),
        ),
    )

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("[b]Build a campaign, check it, run it[/b]")
            yield Static(
                "[dim]Every field starts at its default, shown dimmed. Problems "
                "appear on the field they concern, and Run stays disabled until "
                "there are none. Running then loads the goals and builds every "
                "model before the first attack, and says what it found.[/dim]"
            )
            for title, rows in self.SECTIONS:
                yield Static(f"\n[b]{title}[/b]")
                for keys, what in rows:
                    yield Static(f"  [b]{keys:<7}[/b] [dim]{escape(what)}[/dim]")
            with Horizontal():
                yield Button("Close", id="ok", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#ok", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)


__all__ = [
    "ConfirmScreen",
    "ExampleScreen",
    "HelpScreen",
    "PathScreen",
    "ResultsScreen",
    "RunScreen",
]
