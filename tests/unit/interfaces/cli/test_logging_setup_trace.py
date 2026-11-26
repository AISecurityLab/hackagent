# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The CLI's terminal log: the file's line, coloured; -v sets its level."""

from __future__ import annotations

import io
import logging
import sys

from rich.console import Console

from hackagent.core.logging import TRACE_LOGGER, PlainFormatter
from hackagent.interfaces.cli.logging_setup import (
    LogLineHandler,
    apply_verbosity,
    shown_level,
)


def _terminal(width: int = 60) -> tuple[LogLineHandler, io.StringIO]:
    out = io.StringIO()
    console = Console(file=out, width=width, force_terminal=True, color_system=None)
    return LogLineHandler(console), out


def _trace(**step) -> logging.LogRecord:
    record = logging.LogRecord(TRACE_LOGGER, logging.INFO, "x.py", 1, "m", None, None)
    record.trace_step = step
    return record


def test_a_terminal_shows_the_line_a_file_has():
    """Same words as a file, the TUI and the platform; one record per line,
    however narrow the terminal."""
    handler, out = _terminal(width=40)
    record = _trace(
        source="pair · goal 1",
        within=["round 2/3", "stream 1/2"],
        what="panel: jailbroken (score 9) · 0.1s",
    )
    handler.handle(record)

    assert out.getvalue().splitlines() == [PlainFormatter().format(record)]


def test_a_message_is_never_read_as_markup():
    handler, out = _terminal()
    record = logging.LogRecord(
        "hackagent.x", logging.WARNING, "x.py", 1, "[bold]not markup[/bold]", None, None
    )
    handler.handle(record)

    assert "[bold]not markup[/bold]" in out.getvalue()


def test_a_traceback_is_drawn_below_its_line():
    handler, out = _terminal(width=100)
    try:
        raise ValueError("the reason")
    except ValueError:
        record = logging.LogRecord(
            "hackagent.x", logging.ERROR, "x.py", 1, "it failed", None, sys.exc_info()
        )
    handler.handle(record)

    first, *rest = out.getvalue().splitlines()
    assert first.endswith("ERROR   it failed")
    assert any("ValueError" in line and "the reason" in line for line in rest)


def test_verbosity_sets_the_level_unless_the_environment_does(monkeypatch):
    # apply_verbosity keeps the count for suppress_noisy_libraries, and at
    # -vvv opens the root logger: neither may outlast this test.
    import hackagent.interfaces.cli.logging_setup as logging_setup

    monkeypatch.setattr(logging_setup, "_verbosity", logging_setup._verbosity)
    monkeypatch.setattr(logging.getLogger(), "level", logging.getLogger().level)
    logger = logging.getLogger("hackagent")
    level = logger.level
    handlers = [(handler, handler.level) for handler in logger.handlers]
    try:
        monkeypatch.delenv("HACKAGENT_LOG_LEVEL", raising=False)
        # What the CLI's log shows, with or without the CLI's handler.
        # None: the run's log from INFO; -v and more: every call too.
        apply_verbosity(0)
        assert shown_level() == logging.INFO
        apply_verbosity(5)
        assert shown_level() == logging.DEBUG
        monkeypatch.setenv("HACKAGENT_LOG_LEVEL", "ERROR")
        apply_verbosity(0)
        assert shown_level() == logging.DEBUG
    finally:
        logger.setLevel(level)
        for handler, was in handlers:
            handler.setLevel(was)
