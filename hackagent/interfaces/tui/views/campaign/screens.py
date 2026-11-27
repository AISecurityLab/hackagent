# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The screens the builder opens: the run view, and small dialogs."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Iterable
from typing import Any, Callable, Mapping, Optional, Sequence

from rich.markup import escape
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import (
    Button,
    Footer,
    Input,
    Label,
    OptionList,
    RichLog,
    Static,
)
from textual.widgets.option_list import Option

from hackagent.interfaces.palette import ACCENT, NAME, SECONDARY
from hackagent.interfaces.tui.frame import FramedScreen
from hackagent.interfaces.tui.keys import key

_DIALOG_CSS = """
{name} {{ align: center middle; background: $background 60%; }}
{name} > Vertical {{
    width: 64; height: auto; padding: 1 2;
    border: round $primary; background: $surface;
}}
{name} Horizontal {{ height: auto; margin-top: 1; }}
{name} Button {{ width: 1fr; margin: 0 1 0 0; }}
"""


#: How many of a run's lines the run view keeps and shows: the latest.
RUN_LINES = 5000


class ExampleScreen(FramedScreen[Optional[Path]]):
    """Pick one of the shipped examples, from a tree of the folders they are
    in, drawn open: each example on one line and what it is for on the next.
    Dismisses with its path, or None."""

    TITLE_TEXT = "Start from an example"
    CONTEXT_TEXT = "it opens in the builder: read it, change the model, then run it"

    DEFAULT_CSS = """
    ExampleScreen OptionList { height: 1fr; border: none; padding: 1 1 0 1; }
    /* A folder is a heading, not a choice: in its own colours, not greyed. */
    ExampleScreen OptionList > .option-list--option-disabled {
        color: $text; text-style: none;
    }
    """

    # The screen's own, ahead of the list's, so the footer says what the
    # keys do here.
    BINDINGS = [
        key("choose", "move('down')", priority=True),
        key("choose", "move('up')", show=False, priority=True, keys="up"),
        key("open", priority=True),
        key("back", "dismiss(None)"),
    ]

    def __init__(self, examples: Mapping[str, Path]) -> None:
        super().__init__()
        self._examples = dict(examples)

    def body(self) -> Iterable[Widget]:
        yield OptionList(*_example_tree(self._examples), id="examples")

    def on_mount(self) -> None:
        listing = self.query_one(OptionList)
        listing.focus()
        # Nothing chosen until you move: a bar on the first example before
        # anything was pressed reads as a choice someone else made.
        listing.highlighted = None

    def action_move(self, direction: str) -> None:
        """Move to the next or the previous example."""
        listing = self.query_one(OptionList)
        listing.focus()
        listing.action_cursor_down() if direction == "down" else listing.action_cursor_up()

    def action_open(self) -> None:
        """Open the highlighted example."""
        self.query_one(OptionList).action_select()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.dismiss(self._examples.get(str(event.option.id)))


#: How the example tree is drawn: its guides, folders and subfolders, the
#: campaigns in them, and what each campaign is for.
_GUIDE, _FOLDER, _CAMPAIGN, _ABOUT = (
    SECONDARY,
    f"bold {ACCENT}",
    f"bold {NAME}",
    SECONDARY,
)


def _example_tree(examples: Mapping[str, Path]) -> list[Option]:
    """The examples as the folders and subfolders they are in, every folder
    open: a folder is a heading (it cannot be chosen), a campaign a choice
    of two lines, its name and its own description. Folders first, both in
    name order."""
    from hackagent import examples as examples_catalog

    nested: dict[str, Any] = {}
    for name, path in examples.items():
        *folders, leaf = name.split("/")
        level = nested
        for folder in folders:
            level = level.setdefault(folder, {})
        level[leaf] = name

    options: list[Option] = []

    def add(level: Mapping[str, Any], indent: str, depth: int) -> None:
        top = depth == 0
        folders = sorted(k for k, v in level.items() if isinstance(v, dict))
        leaves = sorted(k for k, v in level.items() if not isinstance(v, dict))
        entries = [(folder, True) for folder in folders] + [
            (leaf, False) for leaf in leaves
        ]
        for position, (entry, is_folder) in enumerate(entries):
            last = position == len(entries) - 1
            branch = "" if top else ("└─ " if last else "├─ ")
            below = indent + ("" if top else ("   " if last else "│  "))
            if is_folder:
                options.append(
                    Option(
                        Text.assemble(
                            (indent + branch, _GUIDE),
                            (f"{entry}/", _FOLDER),
                        ),
                        disabled=True,
                    )
                )
                add(level[entry], below, depth + 1)
                continue
            name = level[entry]
            about = examples_catalog.describe(examples[name])
            options.append(
                Option(
                    Text.assemble(
                        (indent + branch, _GUIDE),
                        (entry, _CAMPAIGN),
                        "\n",
                        (below, _GUIDE),
                        (about, _ABOUT),
                    ),
                    id=name,
                )
            )

    add(nested, "", 0)
    return options


class ResultsScreen(FramedScreen[None]):
    """Past runs, on a screen of their own."""

    TITLE_TEXT = "Results"

    BINDINGS = [key("back", "close")]

    def __init__(self, cli_config: Any) -> None:
        super().__init__()
        self._cli_config = cli_config

    def body(self) -> Iterable[Widget]:
        from hackagent.interfaces.tui.views.results import ResultsTab

        yield ResultsTab(self._cli_config)

    def action_close(self) -> None:
        self.dismiss(None)


class RunScreen(FramedScreen[None]):
    """A running campaign, with the whole terminal to show it.

    The builder owns the run and keeps every line it has produced; this
    screen renders them. Leaving does not stop anything — the run carries on
    and reopening replays what was missed.
    """

    CONTEXT_TEXT = "leaving does not stop the run · edits apply to the next run"

    DEFAULT_CSS = """
    RunScreen #run-log { height: 1fr; padding: 1 1 0 1; }
    """

    BINDINGS = [
        key("back", "close"),
        key("stop"),
    ]

    def __init__(
        self,
        title: str,
        lines: Sequence[str],
        stop: Callable[[], None],
    ) -> None:
        super().__init__()
        self.TITLE_TEXT = f"Run · {escape(title)}"
        #: The lines to show once mounted: those logged before the screen
        #: opened, then any written before it mounted, in that order.
        self._pending: Optional[list[str]] = list(lines)
        self._stop = stop

    def body(self) -> Iterable[Widget]:
        yield RichLog(markup=True, wrap=True, max_lines=RUN_LINES, id="run-log")

    def on_mount(self) -> None:
        log = self.query_one("#run-log", RichLog)
        for line in self._pending or ():
            log.write(line)
        self._pending = None

    def write(self, markup: str) -> None:
        """Show a line, after every line logged before it."""
        if self._pending is not None:
            self._pending.append(markup)
            return
        self.query_one("#run-log", RichLog).write(markup)

    def action_close(self) -> None:
        self.dismiss(None)

    def action_stop(self) -> None:
        self._stop()


class PathScreen(ModalScreen[Optional[str]]):
    DEFAULT_CSS = _DIALOG_CSS.format(name="PathScreen")
    BINDINGS = [key("back", "dismiss(None)")]

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
        yield Footer()

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
    BINDINGS = [key("back", "dismiss(False)")]

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
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#cancel", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "ok")


class HelpScreen(ModalScreen[None]):
    """What the screen it is opened on is for, and every key it answers to,
    read from its bindings (:mod:`hackagent.interfaces.tui.keys`)."""

    DEFAULT_CSS = _DIALOG_CSS.format(name="HelpScreen").replace(
        "width: 64;", "width: 72;"
    )
    BINDINGS = [
        key("back", "dismiss(None)"),
        key("help", "dismiss(None)"),
    ]

    def __init__(self, rows: Sequence[tuple[str, str]], about: str = "") -> None:
        super().__init__()
        self._rows = list(rows)
        self._about = about

    def compose(self) -> ComposeResult:
        width = max((len(keys) for keys, _ in self._rows), default=0)
        with Vertical():
            yield Static("[b]Keys[/b]")
            if self._about:
                yield Static(f"[dim]{escape(self._about)}[/dim]\n")
            for keys, what in self._rows:
                yield Static(f"  [b]{escape(keys.ljust(width))}[/b]  {escape(what)}")
        yield Footer()


__all__ = [
    "ConfirmScreen",
    "ExampleScreen",
    "HelpScreen",
    "PathScreen",
    "ResultsScreen",
    "RunScreen",
]
