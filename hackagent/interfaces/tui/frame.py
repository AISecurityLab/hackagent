# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The frame every full screen of the TUI shares.

A screen is a title bar (:class:`TitleBar`: what it is, and on the right
what is worth knowing about it now), its content in a box (``frame-body``),
and the app's footer, which lists its keys (:mod:`.keys`). Nothing else
writes keys or hints at the bottom of a screen. :class:`FramedScreen`
composes the three; the main screen, the builder, has the same title bar
and footer.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Optional, TypeVar

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Footer, Static

R = TypeVar("R")


class TitleBar(Horizontal):
    """One line at the top of a screen: its title, bold, and its context,
    dimmed and on the right."""

    DEFAULT_CSS = """
    TitleBar { height: 1; padding: 0 1; background: $panel; }
    /* The gap keeps a long context from running into the title. */
    TitleBar #title { width: auto; text-style: bold; margin-right: 2; }
    TitleBar #context {
        width: 1fr; color: $text-muted; text-align: right;
        text-wrap: nowrap; text-overflow: ellipsis;
    }
    """

    def __init__(self, title: str = "", context: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        # Made here, not in compose: a screen says its title while it is
        # still mounting, before compose has run.
        self._heading = Static(title, id="title")
        self._about = Static(context, id="context")

    def compose(self) -> ComposeResult:
        yield self._heading
        yield self._about

    def show(self, title: Optional[str] = None, context: Optional[str] = None) -> None:
        """Say a new title or context (Rich markup); ``None`` keeps it."""
        if title is not None:
            self._heading.update(title)
        if context is not None:
            self._about.update(context)


class FramedScreen(Screen[R]):
    """A full screen in the shared frame: :class:`TitleBar`, :meth:`body`,
    and the footer."""

    #: The title bar's title and context when the screen opens.
    TITLE_TEXT = ""
    CONTEXT_TEXT = ""

    DEFAULT_CSS = """
    FramedScreen { background: $surface; }
    """

    def compose(self) -> ComposeResult:
        yield TitleBar(self.TITLE_TEXT, self.CONTEXT_TEXT)
        with Vertical(classes="frame-body"):
            yield from self.body()
        yield Footer()

    def body(self) -> Iterable[Widget]:
        """The screen's content, between the title bar and the footer."""
        return ()

    @property
    def title_bar(self) -> TitleBar:
        return self.query_one(TitleBar)


def title_bar(widget: Widget) -> Optional[TitleBar]:
    """The title bar of the screen ``widget`` is on, if it has one."""
    found = widget.screen.query(TitleBar)
    return found.first() if found else None


__all__ = ["FramedScreen", "TitleBar", "title_bar"]
