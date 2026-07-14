# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Integration tests for multi-attack selection in the Attacks tab.

Covers the SelectionList-based strategy picker: it defaults to the
Jailbreak evaluation campaign's primary attacks (h4rm3l -> TAP -> PAIR),
matching HackAgent.hack_chain's default. Checking a single attack must
behave exactly as before (HackAgent.hack), while checking 2+ attacks must
build a per-step attack_config list and execute via HackAgent.hack_chain,
with a user-controllable "escalate only mitigated" flag.
"""

from unittest.mock import MagicMock, patch

import pytest
from textual.app import App
from textual.widgets import Checkbox, Input, Select, SelectionList, Static

from hackagent.cli.config import CLIConfig
from hackagent.cli.tui.views.attacks import AttacksTab, _default_campaign_attack_keys


@pytest.fixture
def cli_config():
    config = MagicMock(spec=CLIConfig)
    config.api_key = "test-api-key-12345"
    config.base_url = "https://api.test.hackagent.dev"
    return config


def _fill_required_fields(tab: AttacksTab) -> None:
    tab.query_one("#agent-name", Input).value = "my-agent"
    tab.query_one("#endpoint-url", Input).value = "http://localhost:8000"


def _select_only(tab: AttacksTab, keys) -> None:
    """Reduce the strategy selection to exactly `keys`, in that order."""
    selection_list = tab.query_one("#attack-strategies", SelectionList)
    selection_list.deselect_all()
    for key in keys:
        selection_list.select(key)


class TestStrategySelectionDefaults:
    @pytest.mark.asyncio
    async def test_defaults_to_jailbreak_campaign_in_order(self, cli_config):
        class TestApp(App):
            def compose(self):
                yield AttacksTab(cli_config)

        app = TestApp()
        async with app.run_test() as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            selection_list = tab.query_one("#attack-strategies", SelectionList)
            assert selection_list.selected == ["h4rm3l", "tap", "pair"]
            assert selection_list.selected == _default_campaign_attack_keys()

    @pytest.mark.asyncio
    async def test_escalate_toggle_visible_by_default(self, cli_config):
        """The campaign default has 3 attacks selected, so the escalate
        toggle (only relevant for 2+ attacks) is visible out of the box."""

        class TestApp(App):
            def compose(self):
                yield AttacksTab(cli_config)

        app = TestApp()
        async with app.run_test() as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            assert tab.query_one("#escalate-only-mitigated", Checkbox).display is True
            assert (
                tab.query_one("#escalate-only-mitigated-help", Static).display is True
            )

    @pytest.mark.asyncio
    async def test_escalate_toggle_hidden_with_single_selection(self, cli_config):
        class TestApp(App):
            def compose(self):
                yield AttacksTab(cli_config)

        app = TestApp()
        async with app.run_test() as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            _select_only(tab, ["h4rm3l"])
            await pilot.pause()

            assert tab.query_one("#escalate-only-mitigated", Checkbox).display is False
            assert (
                tab.query_one("#escalate-only-mitigated-help", Static).display is False
            )

    @pytest.mark.asyncio
    async def test_clear_form_resets_to_default_campaign(self, cli_config):
        class TestApp(App):
            def compose(self):
                yield AttacksTab(cli_config)

        app = TestApp()
        async with app.run_test() as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            selection_list = tab.query_one("#attack-strategies", SelectionList)

            _select_only(tab, ["baseline"])
            await pilot.pause()
            assert selection_list.selected == ["baseline"]

            tab._clear_form()
            await pilot.pause()
            assert selection_list.selected == ["h4rm3l", "tap", "pair"]


class TestConfiguringDropdownRestrictedToSelection:
    """The 'Configuring' Select must only ever offer checked strategies —
    you shouldn't be able to open the config form for an attack that isn't
    actually part of the current run."""

    @pytest.mark.asyncio
    async def test_dropdown_lists_only_checked_strategies_by_default(self, cli_config):
        class TestApp(App):
            def compose(self):
                yield AttacksTab(cli_config)

        app = TestApp()
        async with app.run_test() as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            focus_select = tab.query_one("#attack-strategy-focus", Select)
            option_values = [
                value for _, value in focus_select._options if value != Select.NULL
            ]
            assert option_values == ["h4rm3l", "tap", "pair"]

    @pytest.mark.asyncio
    async def test_dropdown_shrinks_when_selection_shrinks(self, cli_config):
        class TestApp(App):
            def compose(self):
                yield AttacksTab(cli_config)

        app = TestApp()
        async with app.run_test() as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            _select_only(tab, ["h4rm3l"])
            await pilot.pause()

            focus_select = tab.query_one("#attack-strategy-focus", Select)
            option_values = [
                value for _, value in focus_select._options if value != Select.NULL
            ]
            assert option_values == ["h4rm3l"]
            assert focus_select.value == "h4rm3l"

    @pytest.mark.asyncio
    async def test_focus_switches_away_when_focused_strategy_is_unchecked(
        self, cli_config
    ):
        class TestApp(App):
            def compose(self):
                yield AttacksTab(cli_config)

        app = TestApp()
        async with app.run_test() as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            tab._switch_focused_strategy("tap")
            await pilot.pause()
            assert tab._focused_strategy == "tap"

            # Uncheck "tap" (the currently-focused strategy) — focus and the
            # dropdown's options must both move away from it.
            _select_only(tab, ["h4rm3l", "pair"])
            await pilot.pause()

            focus_select = tab.query_one("#attack-strategy-focus", Select)
            option_values = [value for _, value in focus_select._options]
            assert "tap" not in option_values
            assert tab._focused_strategy in {"h4rm3l", "pair"}
            assert focus_select.value == tab._focused_strategy

    @pytest.mark.asyncio
    async def test_selecting_in_configuring_then_unchecking_it_does_not_crash(
        self, cli_config
    ):
        """Regression test: picking a strategy via the "Configuring" Select
        (posting a real ``Select.Changed`` through the UI, not calling
        ``_switch_focused_strategy`` directly) and then unchecking that same
        strategy from the SelectionList used to raise
        ``NoMatches: No nodes match '#label' on SelectCurrent`` — caused by
        ``Select.BLANK`` (which is just the bool ``False`` in this Textual
        version, not the blank-value sentinel) being misdetected as a real
        selection wherever a blank/`Select.NULL` value briefly passed
        through `on_select_changed`, triggering a spurious extra re-render.
        """

        class TestApp(App):
            def compose(self):
                yield AttacksTab(cli_config)

        app = TestApp()
        async with app.run_test() as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()

            focus_select = tab.query_one("#attack-strategy-focus", Select)
            focus_select.value = "tap"
            await pilot.pause()
            assert tab._focused_strategy == "tap"

            selection_list = tab.query_one("#attack-strategies", SelectionList)
            selection_list.deselect("tap")
            await pilot.pause()

            assert "tap" not in selection_list.selected
            assert tab._focused_strategy in {"h4rm3l", "pair"}
            # No unhandled exception propagated out of run_test() above —
            # that's the actual regression being guarded against.


class TestFocusedStrategyValueCaching:
    @pytest.mark.asyncio
    async def test_switching_focus_away_and_back_preserves_values(self, cli_config):
        class TestApp(App):
            def compose(self):
                yield AttacksTab(cli_config)

        app = TestApp()
        async with app.run_test() as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            first_key, second_key = "h4rm3l", "tap"

            resolved_before = tab._resolve_config_for_strategy(first_key)
            assert resolved_before  # sanity: spec has at least one default field

            tab._switch_focused_strategy(second_key)
            await pilot.pause()
            assert tab._focused_strategy == second_key

            tab._switch_focused_strategy(first_key)
            await pilot.pause()
            assert tab._focused_strategy == first_key

            resolved_after = tab._resolve_config_for_strategy(first_key)
            assert resolved_after == resolved_before


class TestExecuteAttackChainBuilding:
    """`_execute_attack(dry_run=True)` never spawns a worker thread, so the
    chain-building branch can be exercised synchronously by inspecting the
    preview text written to the status widget."""

    @pytest.mark.asyncio
    async def test_dry_run_single_strategy_uses_singular_attack_config(
        self, cli_config
    ):
        class TestApp(App):
            def compose(self):
                yield AttacksTab(cli_config)

        app = TestApp()
        async with app.run_test() as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            _fill_required_fields(tab)
            _select_only(tab, ["h4rm3l"])
            await pilot.pause()

            tab._execute_attack(dry_run=True)

            text = str(tab.query_one("#execution-status", Static).render())
            assert "Escalate Only Mitigated" not in text
            assert "h4rm3l" in text

    @pytest.mark.asyncio
    async def test_dry_run_default_campaign_builds_chain_preview(self, cli_config):
        class TestApp(App):
            def compose(self):
                yield AttacksTab(cli_config)

        app = TestApp()
        async with app.run_test() as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            _fill_required_fields(tab)

            tab._execute_attack(dry_run=True)

            text = str(tab.query_one("#execution-status", Static).render())
            assert "Escalate Only Mitigated" in text
            assert "h4rm3l" in text
            assert "tap" in text
            assert "pair" in text


class TestExecuteAttackDispatch:
    """Verify Execute routes to HackAgent.hack vs HackAgent.hack_chain based
    on how many strategies are checked."""

    @pytest.mark.asyncio
    async def test_single_strategy_calls_hack_not_hack_chain(self, cli_config):
        class TestApp(App):
            def compose(self):
                yield AttacksTab(cli_config)

        app = TestApp()
        async with app.run_test() as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            _fill_required_fields(tab)
            _select_only(tab, ["h4rm3l"])
            await pilot.pause()

            mock_agent_instance = MagicMock()
            mock_agent_instance.hack.return_value = []
            with patch(
                "hackagent.HackAgent",
                return_value=mock_agent_instance,
            ):
                tab._execute_attack(dry_run=False)
                await app.workers.wait_for_complete()

            mock_agent_instance.hack.assert_called_once()
            mock_agent_instance.hack_chain.assert_not_called()
            called_kwargs = mock_agent_instance.hack.call_args.kwargs
            assert called_kwargs["attack_config"]["attack_type"] == "h4rm3l"

    @pytest.mark.asyncio
    async def test_default_campaign_calls_hack_chain_not_hack(self, cli_config):
        class TestApp(App):
            def compose(self):
                yield AttacksTab(cli_config)

        app = TestApp()
        async with app.run_test() as pilot:
            tab = app.query_one(AttacksTab)
            await pilot.pause()
            _fill_required_fields(tab)

            # Uncheck escalate-only-mitigated to verify the flag is forwarded.
            tab.query_one("#escalate-only-mitigated", Checkbox).value = False

            mock_agent_instance = MagicMock()
            mock_agent_instance.hack_chain.return_value = []
            with patch(
                "hackagent.HackAgent",
                return_value=mock_agent_instance,
            ):
                tab._execute_attack(dry_run=False)
                await app.workers.wait_for_complete()

            mock_agent_instance.hack_chain.assert_called_once()
            mock_agent_instance.hack.assert_not_called()
            called_kwargs = mock_agent_instance.hack_chain.call_args.kwargs
            attacks = called_kwargs["attacks"]
            assert [a["attack_type"] for a in attacks] == ["h4rm3l", "tap", "pair"]
            assert called_kwargs["escalate_only_mitigated"] is False
            assert called_kwargs["goals"] == ["Return fake weather data"]

            assert called_kwargs["escalate_only_mitigated"] is False
            assert called_kwargs["goals"] == ["Return fake weather data"]
