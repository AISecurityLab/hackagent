# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Off a terminal, every record is one plain line: date and time, level,
message; a trace record's message is a breadcrumb."""

from __future__ import annotations

import logging
import re

import pytest

from hackagent.core.logging import TRACE_LOGGER, plain_line, trace_breadcrumb
from hackagent.interfaces.cli import logging_setup
from hackagent.interfaces.cli.logging_setup import (
    PlainFormatter,
    log_text,
)

LINE = re.compile(r"^\d\d-\d\d \d\d:\d\d:\d\d (?P<level>[A-Z]+) +(?P<message>.*)$")


def record(name, message, **extra):
    record = logging.LogRecord(
        name, logging.INFO, "/x/runner.py", 310, message, None, None
    )
    record.__dict__.update(extra)
    return record


def test_an_ordinary_record_is_one_dated_line():
    line = PlainFormatter().format(record("hackagent.runner", "baseline started"))
    match = LINE.match(line)
    assert (match["level"], match["message"]) == ("INFO", "baseline started")
    assert "\n" not in line and "runner.py" not in line


def test_a_trace_record_reads_as_a_breadcrumb():
    step = {
        "source": "bon · goal 18",
        "within": ["step 2/2", "candidate #3"],
        "what": "panel: jailbroken (score 10) · 0.1s",
    }
    line = PlainFormatter().format(record(TRACE_LOGGER, "ignored", trace_step=step))
    assert LINE.match(line)["message"] == (
        "bon · goal 18 · step 2/2 · candidate #3 · panel: jailbroken (score 10) · 0.1s"
    )
    assert trace_breadcrumb({"source": "pair · goal 1", "what": "stopped: done"}) == (
        "pair · goal 1 · stopped: done"
    )


def test_every_message_starts_in_the_same_column():
    lines = [plain_line(level, "x", 1.0) for level in ("INFO", "DEBUG", "WARNING")]
    assert len({line.index("x") for line in lines}) == 1


def _styles(text):
    """Each styled stretch of ``text``, as ``(substring, style)``."""
    return {(text.plain[span.start : span.end], str(span.style)) for span in text.spans}


def test_a_coloured_line_reads_as_the_file_s_line():
    """The TUI's line is the file's, character for character, coloured."""
    info = record(
        "hackagent.runner",
        "baseline · goal 1 · result: jailbroken at attempt 2",
        subject={"attack": "baseline", "goal": 1},
    )
    text = log_text(info)

    assert text.plain == PlainFormatter().format(info)
    styles = _styles(text)
    assert (text.plain[:14], "dim") in styles
    assert ("INFO", "green") in styles
    assert ("baseline", logging_setup._attack_style("baseline")) in styles
    assert ("jailbroken", "bold red") in styles


def test_a_line_s_level_sets_its_colour():
    warning = record("hackagent.runner", "a [bold]bracket[/bold] stays text")
    warning.levelno, warning.levelname = logging.WARNING, "WARNING"
    text = log_text(warning)

    assert ("WARNING", "yellow") in _styles(text)
    assert "[bold]bracket[/bold]" in text.plain


@pytest.mark.parametrize(
    "message",
    [
        "pair · 0 jailbroken · 10 jailbroken",
        "pair finished · 0 of 20 goals jailbroken · 10 attempts (10 jailbroken)",
        "pair finished · 0 of 1 goal jailbroken · 10 jailbroken",
    ],
)
def test_none_jailbroken_is_not_picked_out(message):
    """A count of none is no news, however it is counted."""
    text = log_text(record("hackagent.runner", message))
    [(span)] = [s for s in text.spans if str(s.style) == "bold red"]
    assert text.plain[span.start - 3 : span.end] == "10 jailbroken"


def test_a_message_with_line_breaks_stays_one_line():
    line = PlainFormatter().format(
        record("py.warnings", "x.py:3: UserWarning: careful\n  warnings.warn(msg)\n")
    )
    assert "\n" not in line
    assert LINE.match(line)["message"] == (
        "x.py:3: UserWarning: careful ⏎ warnings.warn(msg)"
    )


def test_a_record_with_a_traceback_stays_one_line():
    try:
        raise ValueError("bad reply")
    except ValueError:
        import sys

        failed = record("hackagent.runner", "call failed", exc_info=sys.exc_info())

    line = PlainFormatter().format(failed)

    assert "\n" not in line
    message = LINE.match(line)["message"]
    assert message.startswith("call failed ⏎ Traceback (most recent call last):")
    assert message.endswith("ValueError: bad reply")


def test_logs_go_to_stderr_so_stdout_stays_command_output(monkeypatch):
    import sys

    monkeypatch.setattr(logging_setup, "logs_to_terminal", lambda: False)
    handler = logging_setup._handler()
    assert handler.stream is sys.stderr
