# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""show_run(): what ``campaign run`` and ``run`` print on stdout beside the
log, read from the run's own log records."""

from __future__ import annotations

import logging

import pytest

from hackagent.core.logging import CAMPAIGN_LOGGER, GOALS_LOGGER
from hackagent.interfaces.cli.logging_setup import show_run


@pytest.fixture
def quiet_log():
    """The package logger as the CLI leaves it by default: open, with the
    CLI's handler showing warnings only. Yields that handler."""
    package = logging.getLogger("hackagent")
    level, handlers = package.level, list(package.handlers)
    cli = logging.NullHandler(logging.WARNING)
    cli.hackagent_cli = True
    package.handlers[:] = [cli]
    package.setLevel(logging.DEBUG)
    disabled = logging.root.manager.disable
    logging.disable(logging.NOTSET)
    yield cli
    logging.disable(disabled)
    package.handlers[:] = handlers
    package.setLevel(level)


def _a_run() -> None:
    campaign = logging.getLogger(CAMPAIGN_LOGGER)
    campaign.info("baseline started · 1 goal")
    logging.getLogger(GOALS_LOGGER).info("baseline · goal 1 · result: mitigated")
    logging.getLogger("hackagent.orchestrator.campaign.preflight").info(
        "preflight · 2 models reachable"
    )
    campaign.info("baseline finished")


def test_json_leaves_stdout_to_the_summary(quiet_log, capsys):
    with show_run(as_json=True):
        _a_run()

    assert capsys.readouterr().out == ""


def test_a_quiet_log_still_tells_the_campaign_s_own_lines(quiet_log, capsys):
    """Only the campaign's story: no goal results, no other module's lines."""
    with show_run(as_json=False):
        _a_run()

    out = capsys.readouterr().out.splitlines()
    assert [line.split(None, 3)[3] for line in out] == [
        "baseline started · 1 goal",
        "baseline finished",
    ]


def test_a_log_at_info_already_says_it(quiet_log, capsys):
    quiet_log.setLevel(logging.INFO)
    with show_run(as_json=False):
        _a_run()

    assert capsys.readouterr().out == ""
