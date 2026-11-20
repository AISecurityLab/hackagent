# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Off a terminal, every record is one plain line: date and time, level,
message; a trace record's message is a breadcrumb."""

from __future__ import annotations

import logging
import re

from hackagent.core.logging import TRACE_LOGGER
from hackagent.interfaces.cli.commands.campaign import _summary_lines
from hackagent.interfaces.cli.logging_setup import (
    PlainFormatter,
    plain_line,
    trace_breadcrumb,
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


def test_the_summary_is_log_lines_in_a_file():
    lines = _summary_lines(
        {
            "campaign": "demo",
            "succeeded": False,
            "attempt_errors": 2,
            "attacks": [
                {"name": "pair", "attempts": 10, "successes": 3, "error": None},
                {"name": "tap", "attempts": 0, "successes": 0, "error": "timeout"},
            ],
            "output_directory": "./logs/runs",
        }
    )
    assert lines == [
        (
            "WARNING",
            "campaign demo failed · 2 attacks · 10 attempts · 3 jailbroken · 2 attempt errors",
        ),
        ("INFO", "summary · pair · 10 attempts · 3 jailbroken"),
        ("ERROR", "summary · tap · 0 attempts · 0 jailbroken · failed: timeout"),
        ("INFO", "output → ./logs/runs"),
    ]
