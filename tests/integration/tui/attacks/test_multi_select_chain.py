# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Integration tests for the row-based Attacks tab.

The tab is a declarative campaign builder: each attack is an ``AttackRow``
(its technique + its own attacker model + parameters) and each judge is a
``JudgeRow``. The form assembles a ``CampaignSpec`` and runs it through
``run_campaign``. These tests drive the real Textual widgets to cover adding
and removing rows, escalate visibility, and the assembled spec.
"""

from unittest.mock import MagicMock, patch

import pytest
from textual.app import App
from textual.widgets import Button, Checkbox, Input, Select, Static

from hackagent.interfaces.cli.config import CLIConfig
from hackagent.interfaces.tui.theme import css_variables
from hackagent.interfaces.tui.views.attacks import (
    AttacksTab,
    _default_campaign_attack_keys,
)
from hackagent.interfaces.tui.views.attacks.rows import AttackRow, JudgeRow


@pytest.fixture
def cli_config():
    config = MagicMock(spec=CLIConfig)
    config.api_key = "test-api-key-12345"
    config.base_url = "https://api.test.hackagent.dev"
    return config


class AttacksHostApp(App):
    """Mounts AttacksTab standalone, mirroring HackAgentTUI's brand palette."""

    def get_css_variables(self) -> dict[str, str]:
        return {**super().get_css_variables(), **css_variables()}

    def __init__(self, cli_config):
        super().__init__()
        self._cli_config = cli_config

    def compose(self):
        yield AttacksTab(self._cli_config)


def _fill_required_fields(tab: AttacksTab) -> None:
    tab.query_one("#agent-name", Input).value = "my-agent"
    tab.query_one("#endpoint-url", Input).value = "http://localhost:8000"


def _attack_types(tab: AttacksTab) -> list[str]:
    return [row.attack_type() for row in tab.query(AttackRow)]


def _remove_row(tab: AttacksTab, row) -> None:
    button = row.query_one(".remove-row", Button)
    tab._remove_row(button)


class TestDefaults:
    @pytest.mark.asyncio
    async def test_defaults_to_jailbreak_campaign_rows_in_order(self, cli_config):
        app = AttacksHostApp(cli_config)
        async with app.run_test() as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            assert _attack_types(tab) == _default_campaign_attack_keys()
            assert _attack_types(tab) == ["h4rm3l", "tap", "pair"]
            assert len(list(tab.query(JudgeRow))) == 1

    @pytest.mark.asyncio
    async def test_escalate_toggle_visible_with_multiple_attacks(self, cli_config):
        app = AttacksHostApp(cli_config)
        async with app.run_test() as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            assert tab.query_one("#escalate-only-mitigated", Checkbox).display is True
            assert (
                tab.query_one("#escalate-only-mitigated-help", Static).display is True
            )

    @pytest.mark.asyncio
    async def test_escalate_toggle_hidden_with_single_attack(self, cli_config):
        app = AttacksHostApp(cli_config)
        async with app.run_test() as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            rows = list(tab.query(AttackRow))
            _remove_row(tab, rows[2])
            _remove_row(tab, rows[1])
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert len(list(tab.query(AttackRow))) == 1
            assert tab.query_one("#escalate-only-mitigated", Checkbox).display is False


class TestAddRemoveRows:
    @pytest.mark.asyncio
    async def test_add_attack_appends_a_row(self, cli_config):
        app = AttacksHostApp(cli_config)
        async with app.run_test() as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            tab._add_attack_row()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert len(list(tab.query(AttackRow))) == 4

    @pytest.mark.asyncio
    async def test_add_judge_appends_a_row(self, cli_config):
        app = AttacksHostApp(cli_config)
        async with app.run_test() as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            tab._add_judge_row()
            await pilot.pause()
            assert len(list(tab.query(JudgeRow))) == 2

    @pytest.mark.asyncio
    async def test_cannot_remove_the_last_attack(self, cli_config):
        app = AttacksHostApp(cli_config)
        async with app.run_test() as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            rows = list(tab.query(AttackRow))
            _remove_row(tab, rows[2])
            _remove_row(tab, rows[1])
            await app.workers.wait_for_complete()
            await pilot.pause()
            # One row left — removing it is refused.
            last = list(tab.query(AttackRow))[0]
            _remove_row(tab, last)
            await pilot.pause()
            assert len(list(tab.query(AttackRow))) == 1


class TestAssembledSpec:
    @pytest.mark.asyncio
    async def test_dry_run_previews_the_campaign_spec(self, cli_config):
        app = AttacksHostApp(cli_config)
        async with app.run_test() as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            _fill_required_fields(tab)

            tab._execute_attack(dry_run=True)
            await pilot.pause()

            text = str(tab.query_one("#execution-status", Static).render())
            assert "Campaign spec" in text
            assert "h4rm3l" in text and "tap" in text and "pair" in text

    @pytest.mark.asyncio
    async def test_execute_runs_the_assembled_spec(self, cli_config):
        app = AttacksHostApp(cli_config)
        async with app.run_test() as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            _fill_required_fields(tab)
            # Reduce to a single static attack so no attacker is required and
            # the assembled spec is small.
            rows = list(tab.query(AttackRow))
            _remove_row(tab, rows[2])
            _remove_row(tab, rows[1])
            await app.workers.wait_for_complete()
            await pilot.pause()
            tab.query_one(AttackRow).query_one(
                ".row-attack-type", Select
            ).value = "flipattack"
            await pilot.pause()

            class _Result:
                attacks = ()

            session = MagicMock()
            with (
                patch("hackagent.HackAgent", return_value=session),
                patch(
                    "hackagent.orchestrator.campaign.run_campaign",
                    return_value=_Result(),
                ) as run,
            ):
                tab._execute_attack(dry_run=False)
                await app.workers.wait_for_complete()

            run.assert_called_once()
            spec = run.call_args.args[0]
            assert [a["name"] for a in spec["attacks"]] == ["flipattack"]
            assert spec["target"]["name"] == "my-agent"
            assert run.call_args.kwargs["store"] is session.backend

    @pytest.mark.asyncio
    async def test_multiple_judges_form_the_panel_with_aggregation(self, cli_config):
        app = AttacksHostApp(cli_config)
        async with app.run_test() as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            _fill_required_fields(tab)
            tab._add_judge_row()
            await pilot.pause()
            tab.query_one("#judge-aggregation", Select).value = "mean"

            tab._execute_attack(dry_run=True)
            await pilot.pause()

            campaign = tab._build_campaign_spec(
                agent_name="my-agent",
                agent_type="openai",
                endpoint="http://localhost:8000",
                timeout=300,
                attack_rows=list(tab.query(AttackRow)),
                reject=lambda _m: None,
            )
            assert len(campaign["evaluation"]["judges"]) == 2
            assert campaign["evaluation"]["aggregation"] == "mean"


class TestWizard:
    @pytest.mark.asyncio
    async def test_starts_on_target_step_with_back_disabled(self, cli_config):
        from textual.widgets import ContentSwitcher

        app = AttacksHostApp(cli_config)
        async with app.run_test(size=(120, 45)) as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            assert (
                tab.query_one("#wizard-steps", ContentSwitcher).current == "step-target"
            )
            assert tab.query_one("#wizard-back", Button).disabled is True

    @pytest.mark.asyncio
    async def test_next_is_gated_by_target_validation(self, cli_config):
        from textual.widgets import ContentSwitcher

        app = AttacksHostApp(cli_config)
        async with app.run_test(size=(120, 45)) as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            switcher = tab.query_one("#wizard-steps", ContentSwitcher)

            # Empty target → Next is refused with a message.
            tab._next_step()
            await pilot.pause()
            assert switcher.current == "step-target"
            assert "agent name" in str(
                tab.query_one("#validation-errors", Static).render()
            )

            # Filled target → Next advances.
            _fill_required_fields(tab)
            tab.query_one("#agent-type", Select).value = "openai"
            tab._next_step()
            await pilot.pause()
            assert switcher.current == "step-attacks"

    @pytest.mark.asyncio
    async def test_run_step_shows_a_summary(self, cli_config):
        app = AttacksHostApp(cli_config)
        async with app.run_test(size=(120, 45)) as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            _fill_required_fields(tab)
            tab.query_one("#agent-type", Select).value = "openai"
            tab._go_to_step(3)
            await pilot.pause()
            summary = str(tab.query_one("#run-summary", Static).render())
            assert "my-agent" in summary
            assert "h4rm3l" in summary


class TestRowLayout:
    @staticmethod
    async def _expanded_row_height(cli_config, terminal_height: int) -> int:
        from textual.widgets import Collapsible

        app = AttacksHostApp(cli_config)
        async with app.run_test(size=(120, terminal_height)) as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            row = list(tab.query(AttackRow))[1]
            row.query_one(Collapsible).collapsed = False
            await pilot.pause()
            await pilot.pause()
            return row.outer_size.height

    @pytest.mark.asyncio
    async def test_expanded_row_is_content_sized_not_viewport_sized(self, cli_config):
        """The Parameters container must size to its content. A bare Vertical
        defaults to ``height: 1fr`` and balloons to fill the viewport, which
        made the oversized rows overlap; at ``height: auto`` the same expanded
        row is the same height regardless of terminal size."""
        short = await self._expanded_row_height(cli_config, 40)
        tall = await self._expanded_row_height(cli_config, 80)
        assert short == tall

    @pytest.mark.asyncio
    async def test_rows_do_not_overlap_when_parameters_expand(self, cli_config):
        """Every attack row keeps its own vertical band — expanding the rows'
        Parameters must stack them, never draw one over another."""
        from textual.widgets import Collapsible

        app = AttacksHostApp(cli_config)
        async with app.run_test(size=(120, 70)) as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            rows = list(tab.query(AttackRow))
            for row in rows:
                row.query_one(Collapsible).collapsed = False
            await pilot.pause()
            await pilot.pause()

            for upper, lower in zip(rows, rows[1:]):
                assert lower.region.y >= upper.region.y + upper.region.height
