# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Every interface shows the one log a run writes.

One campaign runs once, with every interface's handler attached at once: the
CLI's log as a file has it and as a terminal shows it (``-vvv``), the TUI's
run view, the status lines of a quiet log, the platform's activity relay and
the run's own ``run.log``.
Each must show the same records, in the same order and words, differing only
in the level it chose and the form it draws them in.
"""

from __future__ import annotations

import io
import logging
from queue import SimpleQueue
from types import SimpleNamespace

import pytest
from rich.console import Console
from rich.text import Text

from hackagent.core.logging import (
    PACKAGE_LOGGER,
    TRACE_LOGGER,
    PlainFormatter,
    capture,
    CAMPAIGN_LOGGER,
    GOALS_LOGGER,
)
from hackagent.interfaces.cli.logging_setup import (
    LogLineHandler,
    RunStatusHandler,
)
from hackagent.interfaces.tui.views.campaign.builder import _RunLog
from hackagent.orchestrator.campaign import run_campaign
from hackagent.orchestrator.execution.activity import ActivityRelay
from tests.unit.campaign.fakes import FakeBuilder, ScriptedModel, campaign, goals

REPLY = "Sure, here is the plan"


class _Keep(logging.Handler):
    """The CLI's log as a file has it, every level, with the records."""

    def __init__(self) -> None:
        super().__init__()
        self.setFormatter(PlainFormatter())
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    def lines(self, level: int = logging.DEBUG) -> list[str]:
        return [self.format(r) for r in self.records if r.levelno >= level]


def _message(line: str) -> str:
    """A file line's message: what follows its date, time and level."""
    return line.split(None, 3)[3]


@pytest.fixture
def one_run(tmp_path, monkeypatch, capsys):
    """Run one campaign with every interface listening; what each showed."""
    from tests.fakes import RecordingStore

    monkeypatch.setattr(logging.getLogger(PACKAGE_LOGGER), "level", logging.DEBUG)
    disabled = logging.root.manager.disable
    logging.disable(logging.NOTSET)

    log = _Keep()
    # A narrow terminal: a long line stays one record all the same.
    terminal = io.StringIO()
    console = Console(file=terminal, width=50, force_terminal=True, color_system=None)
    pane: SimpleQueue = SimpleQueue()
    sent: list[dict] = []
    relay = ActivityRelay(sent.extend, interval_s=0.01)
    values = campaign(
        attacks=[{"name": "baseline"}],
        execution={"output": {"directory": str(tmp_path)}},
    )
    try:
        with (
            capture(log, logging.DEBUG),
            capture(LogLineHandler(console), logging.DEBUG),
            capture(_RunLog(pane), logging.INFO),
            relay.capture(),
        ):
            result = run_campaign(
                values,
                build=FakeBuilder(
                    {"target": ScriptedModel(REPLY), "judge": ScriptedModel("yes")}
                ),
                load=goals("goal one", "goal two"),
                store=RecordingStore(),
            )
        relay.close()
    finally:
        logging.disable(disabled)

    return SimpleNamespace(
        log=log,
        terminal=terminal.getvalue().splitlines(),
        pane=[pane.get() for _ in range(pane.qsize())],
        sent=sent,
        run_log=(tmp_path / result.run_id / "run.log")
        .read_text(encoding="utf-8")
        .splitlines(),
    )


def test_the_run_logs_its_story_trace_and_replies(one_run):
    """The run under test says enough for the comparisons to mean something."""
    records = one_run.log.records
    assert any(r.name == CAMPAIGN_LOGGER for r in records)
    assert sum(r.name == GOALS_LOGGER for r in records) == 2
    assert any(r.name == TRACE_LOGGER and r.levelno == logging.INFO for r in records)
    assert any(r.name == TRACE_LOGGER and r.levelno == logging.DEBUG for r in records)
    assert any(REPLY in line for line in one_run.log.lines())


def test_no_line_that_may_leave_quotes_a_reply(one_run):
    """INFO and above may leave the machine: none of it quotes model text."""
    assert not any(REPLY in line for line in one_run.log.lines(logging.INFO))


def test_the_terminal_shows_the_log_file_s_lines(one_run):
    assert one_run.terminal == one_run.log.lines()


def test_the_tui_shows_the_log_file_s_lines(one_run):
    assert [Text.from_markup(markup).plain for markup in one_run.pane] == (
        one_run.log.lines(logging.INFO)
    )


def test_run_log_is_the_log_file_at_info(one_run):
    assert one_run.run_log == one_run.log.lines(logging.INFO)


def test_the_platform_gets_the_lines_from_info(one_run):
    """The same lines, in the log's words, each about its attack and goal."""
    expected = [
        (record.levelname.lower(), _message(line))
        for record, line in zip(one_run.log.records, one_run.log.lines())
        if record.levelno >= logging.INFO
    ]
    assert [(event["level"], event["message"]) for event in one_run.sent] == expected
    results = [e for e in one_run.sent if " · result: " in e["message"]]
    assert {(e["attack"], e["goal_index"]) for e in results} == {
        ("baseline", 0),
        ("baseline", 1),
    }


def test_a_quiet_log_s_status_lines_are_the_campaign_s_lines(one_run, capsys):
    """Off a terminal, the status lines are the file's lines of the campaign
    logger that a log showing only warnings hides."""
    status = RunStatusHandler(hidden_below=logging.WARNING)  # not a terminal here
    for record in one_run.log.records:
        if record.levelno >= logging.INFO:
            status.handle(record)

    out = capsys.readouterr().out.splitlines()
    assert out == [
        PlainFormatter().format(r)
        for r in one_run.log.records
        if r.name == CAMPAIGN_LOGGER and logging.INFO <= r.levelno < logging.WARNING
    ]
    assert out and not any(" · result: " in line for line in out)
