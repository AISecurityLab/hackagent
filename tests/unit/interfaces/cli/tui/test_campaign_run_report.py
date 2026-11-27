# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The run view shows the run's log, as ``hackagent campaign run`` writes it.

Before attacking, the builder resolves the campaign — the checks
``hackagent campaign validate`` runs — and hands what it resolved to the run.
What the run found, and its closing summary, the run logs itself, so the view
and the CLI show the same lines; the view colours them by level.
"""

from __future__ import annotations

import logging
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import yaml
from rich.text import Text

from hackagent.core.contracts import Verdict
from hackagent.core.logging import CAMPAIGN_LOGGER, GOALS_LOGGER, about
from hackagent.interfaces.cli.config import CLIConfig
from hackagent.interfaces.cli.logging_setup import PlainFormatter, _attack_style
from hackagent.interfaces.tui.app import HackAgentTUI
from hackagent.interfaces.tui.views.campaign import CampaignBuilder
from hackagent.interfaces.tui.views.campaign.welcome import starting_point
from hackagent.orchestrator.campaign import (
    AttackOutcome,
    Attempt,
    CampaignResult,
    CampaignSpec,
)

WIDE = (120, 40)


@pytest.fixture
def cli_config():
    config = MagicMock(spec=CLIConfig)
    config.api_key = "test-key"
    config.base_url = "https://api.test.hackagent.dev"
    config.settings = MagicMock(name="resolved-settings")
    return config


def _attempt(success: bool) -> Attempt:
    return Attempt(
        goal_index=0,
        request_index=0,
        goal="a goal",
        verdict=Verdict(success=success, score=1.0 if success else 0.0),
    )


def _result(*attacks: AttackOutcome) -> CampaignResult:
    return CampaignResult(
        campaign_name="demo", run_id="run-1", dry_run=False, attacks=attacks
    )


def _resolution(spec: CampaignSpec, goals: int = 3):
    return SimpleNamespace(
        spec=spec,
        goals=tuple(range(goals)),
        attacks=(SimpleNamespace(name="baseline"),),
        classifier=None,
    )


class TestTheRun:
    """``_execute`` end to end, with resolution and the run itself stubbed."""

    def _app(self, cli_config) -> HackAgentTUI:
        return HackAgentTUI(
            cli_config,
            initial_data={"campaign_yaml": yaml.safe_dump(starting_point().document)},
        )

    @pytest.mark.asyncio
    async def test_the_view_s_own_lines_read_as_log_lines(self, cli_config):
        """What the view adds, it writes as a line of the run's log."""
        app = self._app(cli_config)
        async with app.run_test(size=WIDE) as pilot:
            await pilot.pause()
            builder = app.query_one(CampaignBuilder)
            builder._snapshot = builder.draft.validate()[0]
            with (
                patch(
                    "hackagent.orchestrator.campaign.resolve_campaign",
                    return_value=_resolution(builder._snapshot),
                ),
                patch(
                    "hackagent.orchestrator.campaign.run_campaign",
                    return_value=_result(
                        AttackOutcome(name="baseline", attempts=(_attempt(True),))
                    ),
                ),
                patch.object(app, "call_from_thread", _straight_through),
            ):
                builder._execute()
            lines = _plain(builder._run_lines)

        assert [line.split(None, 3)[2:] for line in lines] == [
            ["INFO", "campaign · checking goals, models and judges"]
        ]

    @pytest.mark.asyncio
    async def test_the_run_attacks_what_the_check_reported(self, cli_config):
        """Resolving twice could load one set of goals and attack another."""
        app = self._app(cli_config)
        async with app.run_test(size=WIDE) as pilot:
            await pilot.pause()
            builder = app.query_one(CampaignBuilder)
            builder._snapshot = builder.draft.validate()[0]
            resolution = _resolution(builder._snapshot)
            captured: dict = {}

            def fake_run(_spec, **kwargs):
                captured.update(kwargs)
                return _result()

            with (
                patch(
                    "hackagent.orchestrator.campaign.resolve_campaign",
                    return_value=resolution,
                ),
                patch(
                    "hackagent.orchestrator.campaign.run_campaign",
                    side_effect=fake_run,
                ),
                patch.object(app, "call_from_thread", _straight_through),
            ):
                builder._execute()

        assert captured["resolved"] is resolution

    @pytest.mark.asyncio
    async def test_a_campaign_that_cannot_be_resolved_is_never_attacked(
        self, cli_config
    ):
        """A valid file can still name a judge with no key behind it."""
        app = self._app(cli_config)
        async with app.run_test(size=WIDE) as pilot:
            await pilot.pause()
            builder = app.query_one(CampaignBuilder)
            builder._snapshot = builder.draft.validate()[0]
            run = MagicMock(name="run_campaign")
            with (
                patch(
                    "hackagent.orchestrator.campaign.resolve_campaign",
                    side_effect=ValueError("no api key for judge"),
                ),
                patch("hackagent.orchestrator.campaign.run_campaign", run),
                patch.object(app, "call_from_thread", _straight_through),
            ):
                builder._execute()
            log = _plain(builder._run_lines)

        run.assert_not_called()
        assert log[-1].split(None, 3)[2:] == [
            "ERROR",
            "campaign rejected: no api key for judge",
        ]
        # The run ended: Run is offered again rather than left disabled.
        assert builder._campaign_running is False

    @pytest.mark.asyncio
    async def test_the_view_shows_the_run_s_log_as_a_log_file_has_it(self, cli_config):
        """The run's records, at the level the log shows, written as the CLI
        writes them to a file and coloured; its events also move the
        progress bar."""
        trace = logging.getLogger("hackagent.trace")
        runner = logging.getLogger(CAMPAIGN_LOGGER)
        goals = logging.getLogger(GOALS_LOGGER)
        package = logging.getLogger("hackagent")
        written: list[logging.LogRecord] = []

        class Keep(logging.Handler):
            def emit(self, record):
                written.append(record)

        def run(*_args, **kwargs):
            assert kwargs["cancel"] is builder._cancel
            with about(attack="baseline"):
                runner.info("baseline started · 2 goals")
            trace.info(
                "baseline · goal 1 · panel: mitigated",
                extra={
                    "trace_step": {
                        "source": "baseline · goal 1",
                        "within": ["round 2/3"],
                        "what": "panel: mitigated",
                    }
                },
            )
            trace.debug("baseline · goal 1 · target: a reply")
            with about(attack="baseline", goal=1, goals=2):
                goals.info("baseline · goal 1 · result: mitigated")
            # Not this run's: logged on a thread the run did not start.
            outside = threading.Thread(target=runner.warning, args=("elsewhere",))
            outside.start()
            outside.join()
            return _result()

        app = self._app(cli_config)
        level = package.level
        keep = Keep()
        async with app.run_test(size=WIDE) as pilot:
            await pilot.pause()
            builder = app.query_one(CampaignBuilder)
            builder._snapshot = builder.draft.validate()[0]
            package.setLevel(logging.INFO)
            trace.addHandler(keep)
            runner.addHandler(keep)
            disabled = logging.root.manager.disable
            logging.disable(logging.NOTSET)
            try:
                with (
                    patch(
                        "hackagent.orchestrator.campaign.resolve_campaign",
                        return_value=_resolution(builder._snapshot),
                    ),
                    patch("hackagent.orchestrator.campaign.run_campaign", run),
                    patch.object(app, "call_from_thread", _straight_through),
                ):
                    builder._execute()
            finally:
                logging.disable(disabled)
                trace.removeHandler(keep)
                runner.removeHandler(keep)
                package.setLevel(level)
            markup = builder._run_lines
            lines = _plain(markup)

        run_s = [
            record
            for record in written
            if record.levelno >= logging.INFO and record.getMessage() != "elsewhere"
        ]
        assert len(run_s) == 3
        for record in run_s:
            assert lines.count(PlainFormatter().format(record)) == 1
        log = "\n".join(lines)
        assert "round 2/3 · panel: mitigated" in log
        assert "target: a reply" not in log
        assert "elsewhere" not in log
        # Coloured: the level by severity, the attack in its own colour.
        [started] = [m for m, line in zip(markup, lines) if "baseline started" in line]
        assert "[green]INFO[/green]" in started
        assert f"[{_attack_style('baseline')}]baseline[/" in started


def _plain(lines: list[str]) -> list[str]:
    """The text of each markup line, as it reads on screen."""
    return [Text.from_markup(line).plain for line in lines]


def _straight_through(callback, *args, **kwargs):
    """Stand in for ``call_from_thread``: the test is already on that thread."""
    return callback(*args, **kwargs)
