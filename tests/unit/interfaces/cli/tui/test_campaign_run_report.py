# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""A run says what it is about to do, and what it did.

Before attacking, the builder resolves the campaign — the checks
``hackagent campaign validate`` runs — and logs what it found; afterwards it
logs the per-attack table ``hackagent campaign run`` prints. The log is the
whole record of a run, so both belong in it.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import yaml

from hackagent.core.contracts import Verdict
from hackagent.interfaces.cli.config import CLIConfig
from hackagent.interfaces.tui.app import HackAgentTUI
from hackagent.interfaces.tui.views.campaign import CampaignBuilder
from hackagent.interfaces.tui.views.campaign.report import attacks_markup, check_markup
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


class TestTheBlocksThemselves:
    def test_the_check_lists_every_row_it_was_given(self):
        block = check_markup({"Goals": "3", "Attacks": "baseline"})

        assert "Goals" in block and "3" in block
        assert "Attacks" in block and "baseline" in block

    def test_an_empty_check_renders_nothing(self):
        assert check_markup({}) == ""

    def test_the_table_reports_attempts_and_successes_per_attack(self):
        block = attacks_markup(
            {
                "attacks": [
                    {"name": "baseline", "attempts": 4, "successes": 1, "error": None},
                    {"name": "pap", "attempts": 2, "successes": 0, "error": None},
                ]
            }
        )
        header, first, second = block.splitlines()

        assert "Attack" in header and "Attempts" in header and "Successes" in header
        assert "baseline" in first and "4" in first and "1" in first
        assert "pap" in second and "2" in second

    def test_an_attack_that_failed_says_why(self):
        block = attacks_markup(
            {
                "attacks": [
                    {
                        "name": "baseline",
                        "attempts": 0,
                        "successes": 0,
                        "error": "target refused every request",
                    }
                ]
            }
        )

        assert "target refused every request" in block

    def test_a_run_with_no_attacks_has_no_table(self):
        """A dry run resolves everything and attacks nothing."""
        assert attacks_markup({"attacks": []}) == ""


class TestTheRun:
    """``_execute`` end to end, with resolution and the run itself stubbed."""

    def _app(self, cli_config) -> HackAgentTUI:
        return HackAgentTUI(
            cli_config,
            initial_data={"campaign_yaml": yaml.safe_dump(starting_point().document)},
        )

    @pytest.mark.asyncio
    async def test_it_reports_what_the_campaign_resolved_to_before_attacking(
        self, cli_config
    ):
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
                        AttackOutcome(
                            name="baseline",
                            attempts=(_attempt(True), _attempt(False)),
                        )
                    ),
                ),
                patch.object(app, "call_from_thread", _straight_through),
            ):
                builder._execute()
            log = "\n".join(builder._run_lines)

        assert "Goals" in log and "3" in log
        # The per-attack table, and then the one-line total.
        assert "Attempts" in log and "Successes" in log
        assert "baseline" in log
        assert "2 attempts" in log and "1 jailbroken" in log

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
            log = "\n".join(builder._run_lines)

        run.assert_not_called()
        assert "no api key for judge" in log
        assert "rejected" in log
        # The run ended: Run is offered again rather than left disabled.
        assert builder._campaign_running is False


def _straight_through(callback, *args, **kwargs):
    """Stand in for ``call_from_thread``: the test is already on that thread."""
    return callback(*args, **kwargs)
