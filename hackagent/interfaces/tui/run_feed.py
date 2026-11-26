# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""A run's log in the TUI, from the run's thread to the run view.

Whatever runs a campaign in the app (the builder, or a run queued from the
dashboard) runs it on a thread of its own, its log captured by a
:class:`RunLog` handler. The handler only queues each line; the app drains
the queue on its own thread (:meth:`RunFeed.drain`), so logging never waits
for a repaint. The feed keeps the latest lines, so the run view
(:class:`~hackagent.interfaces.tui.views.campaign.screens.RunScreen`) can be
left and reopened without losing any.
"""

from __future__ import annotations

import logging
from collections import deque
from queue import Empty, SimpleQueue
from typing import Any, Callable, Optional

from hackagent.interfaces.cli.logging_setup import log_markup

#: How many of a run's lines the run view keeps and shows: the latest.
RUN_LINES = 5000

#: How often the queue is drained, in seconds, and at most how many lines a
#: drain shows, so a burst of lines never holds the screen for long.
DRAIN_S, DRAIN_BATCH = 0.1, 500


class RunLog(logging.Handler):
    """The run view's handler of the run's log: each line, written as the CLI
    writes it to a file and coloured as a log viewer colours it.

    It only queues them for the view, which draws them on its own thread:
    the run never waits for the screen.
    """

    def __init__(self, queue: SimpleQueue[str]) -> None:
        super().__init__()
        self.queue = queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.queue.put(log_markup(record))
        except Exception:
            self.handleError(record)


class RunFeed:
    """One run's lines: queued by its thread, kept, and shown on its run
    view when that view is on top."""

    def __init__(self) -> None:
        self.lines: deque[str] = deque(maxlen=RUN_LINES)
        self.incoming: SimpleQueue[str] = SimpleQueue()
        #: The run view this feed opened, if it did.
        self.screen: Any = None

    def handler(self) -> RunLog:
        """A handler for the run's log, feeding this."""
        return RunLog(self.incoming)

    def clear(self) -> None:
        self.lines.clear()

    def showing(self, app: Any) -> Any:
        """This feed's run view, when it is the screen on top."""
        top = app.screen if app.screen_stack else None
        return top if top is not None and top is self.screen else None

    def log(self, app: Any, markup: str) -> None:
        """Keep a line, and show it if its run view is on top."""
        self.lines.append(markup)
        screen = self.showing(app)
        if screen is not None:
            screen.write(markup)

    def note(self, app: Any, level: int, message: str) -> None:
        """A line of the app's own, written as a line of the run's log."""
        self.log(
            app,
            log_markup(
                logging.makeLogRecord(
                    {
                        "name": __name__,
                        "levelno": level,
                        "levelname": logging.getLevelName(level),
                        "msg": message,
                    }
                )
            ),
        )

    def drain(self, app: Any, limit: Optional[int] = DRAIN_BATCH) -> None:
        """Show what the run's log handed over since the last look, at most
        ``limit`` lines (all of them with ``None``)."""
        taken = 0
        while limit is None or taken < limit:
            try:
                markup = self.incoming.get_nowait()
            except Empty:
                return
            self.log(app, markup)
            taken += 1

    def watch(
        self,
        app: Any,
        title: str,
        stop: Callable[[], None],
        context: Optional[str] = None,
        on_close: Optional[Callable[[Any], None]] = None,
    ) -> None:
        """Open the run view on what the run has produced so far."""
        from hackagent.interfaces.tui.views.campaign.screens import RunScreen

        if self.showing(app) is not None:
            return
        self.screen = RunScreen(title, self.lines, stop, context=context)
        app.push_screen(self.screen, on_close)


__all__ = ["DRAIN_BATCH", "DRAIN_S", "RUN_LINES", "RunFeed", "RunLog"]
