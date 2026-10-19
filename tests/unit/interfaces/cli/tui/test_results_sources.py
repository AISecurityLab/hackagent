# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Results are read from wherever the runs were recorded.

``execution.storage`` is the campaign's choice, so a run can sit on this
machine while the account is remote, and a remote account can be unreachable
from where the campaign was run. The view looks in both places rather than
only the one the account points at, and says which one it is showing.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from hackagent import HackAgent, Settings
from hackagent.core.contracts import EvalStatus
from hackagent.interfaces.cli.config import CLIConfig
from hackagent.interfaces.tui.views.results import ResultsTab
from hackagent.storage.local import LocalBackend


def _session(db_path: str, *, campaign: str = "") -> HackAgent:
    """A session over a throwaway database, holding one campaign or none."""
    store = LocalBackend(db_path=db_path)
    if campaign:
        agent = store.create_or_update_agent(
            name="target",
            agent_type="OPENAI_SDK",
            endpoint="http://host/v1",
            metadata={},
        )
        attack = store.create_attack(
            attack_type="baseline",
            agent_id=agent.id,
            organization=store.get_context().org_id,
            configuration={},
        )
        run_of_campaign = store.create_campaign_run(agent.id, campaign, {})
        run = store.create_run(
            attack.id, agent.id, {"expected_total_goals": 1}, run_of_campaign.id
        )
        result = store.create_result(run.id, "a goal", 0, {}, {})
        store.update_result(
            result.id, evaluation_status=EvalStatus.SUCCESSFUL_JAILBREAK.value
        )
    return HackAgent(
        Settings.resolve(
            api_key="", db_path=db_path, env={}, config_path="/nonexistent"
        ),
        backend=store,
    )


@pytest.fixture
def account_config():
    """A config with an API key: reads would go to the account first."""
    config = MagicMock(spec=CLIConfig)
    config.api_key = "test-key"
    config.base_url = "https://api.test.hackagent.dev"
    config.settings = MagicMock(db_path=":memory:")
    return config


class _Host(App):
    def __init__(self, tab: ResultsTab) -> None:
        super().__init__()
        self._tab = tab

    def compose(self) -> ComposeResult:
        yield self._tab


def _state(tab: ResultsTab) -> tuple[list[str], str]:
    tree = tab.query_one("#results-tree")
    return (
        [str(node.label) for node in tree.root.children],
        str(tab.query_one("#results-hint", Static).render()),
    )


async def _shown(tab: ResultsTab, *, switches: int = 0) -> tuple[list[str], str]:
    """Open the tab, refresh it, and return its campaign lines and hint.

    ``switches`` presses the key that changes store that many times.
    """
    app = _Host(tab)
    async with app.run_test(size=(120, 24)) as pilot:
        await pilot.pause()
        tab.refresh_data()
        for _ in range(switches):
            tab.action_switch_store()
        await pilot.pause()
        return _state(tab)


@pytest.mark.asyncio
async def test_the_account_is_read_when_that_is_where_the_runs_are(
    account_config, tmp_path: Path
):
    tab = ResultsTab(account_config)
    tab.client = lambda: _session(str(tmp_path / "account.db"), campaign="in the cloud")
    tab.local_client = lambda: _session(str(tmp_path / "local.db"))

    labels, hint = await _shown(tab)

    assert any("in the cloud" in label for label in labels)
    assert "the account" in hint


@pytest.mark.asyncio
async def test_a_campaign_stored_here_shows_although_the_account_is_remote(
    account_config, tmp_path: Path
):
    """``execution.storage: local`` records here; the account knows nothing."""
    tab = ResultsTab(account_config)
    tab.client = lambda: _session(str(tmp_path / "account.db"))
    tab.local_client = lambda: _session(
        str(tmp_path / "local.db"), campaign="on my laptop"
    )

    labels, hint = await _shown(tab)

    assert any("on my laptop" in label for label in labels)
    assert "this machine" in hint


@pytest.mark.asyncio
async def test_an_unreachable_account_falls_back_and_says_so(
    account_config, tmp_path: Path
):
    def unreachable():
        raise OSError("Name or service not known")

    tab = ResultsTab(account_config)
    tab.client = unreachable
    tab.local_client = lambda: _session(
        str(tmp_path / "local.db"), campaign="on my laptop"
    )

    labels, hint = await _shown(tab)

    assert any("on my laptop" in label for label in labels)
    assert "this machine" in hint
    assert "s: the account (could not be read)" in hint


@pytest.mark.asyncio
async def test_nothing_readable_anywhere_reports_every_store(
    account_config, tmp_path: Path
):
    def unreachable():
        raise OSError("Name or service not known")

    def no_database():
        raise OSError("unable to open database file")

    tab = ResultsTab(account_config)
    tab.client = unreachable
    tab.local_client = no_database

    _labels, hint = await _shown(tab)

    assert "Could not read results" in hint
    assert "the account: Name or service not known" in hint
    assert "this machine: unable to open database file" in hint


@pytest.mark.asyncio
async def test_without_an_account_only_this_machine_is_read(tmp_path: Path):
    config = MagicMock(spec=CLIConfig)
    config.api_key = None
    config.base_url = "https://api.test.hackagent.dev"
    config.settings = MagicMock(db_path=":memory:")

    account = MagicMock(name="account-session")
    tab = ResultsTab(config)
    tab.client = account
    tab.local_client = lambda: _session(
        str(tmp_path / "local.db"), campaign="on my laptop"
    )

    labels, hint = await _shown(tab)

    account.assert_not_called()
    assert any("on my laptop" in label for label in labels)
    assert "this machine" in hint


@pytest.mark.asyncio
async def test_an_empty_account_and_an_empty_machine_still_say_where_it_looked(
    account_config, tmp_path: Path
):
    tab = ResultsTab(account_config)
    tab.client = lambda: _session(str(tmp_path / "account.db"))
    tab.local_client = lambda: _session(str(tmp_path / "local.db"))

    labels, hint = await _shown(tab)

    assert labels == []
    assert "0 campaigns" in hint and "the account" in hint


@pytest.mark.asyncio
async def test_the_other_store_is_one_key_away(account_config, tmp_path: Path):
    """Both have runs: the one not on screen must still be reachable."""
    tab = ResultsTab(account_config)
    tab.client = lambda: _session(str(tmp_path / "account.db"), campaign="in the cloud")
    tab.local_client = lambda: _session(
        str(tmp_path / "local.db"), campaign="on my laptop"
    )

    labels, hint = await _shown(tab)
    assert any("in the cloud" in label for label in labels)
    assert "s: this machine" in hint

    labels, hint = await _shown(tab, switches=1)
    assert any("on my laptop" in label for label in labels)
    assert "s: the account" in hint


@pytest.mark.asyncio
async def test_a_chosen_store_is_kept_even_when_it_has_nothing(
    account_config, tmp_path: Path
):
    """Asking for the account and being shown the laptop is the old bug."""
    tab = ResultsTab(account_config)
    tab.client = lambda: _session(str(tmp_path / "account.db"))
    tab.local_client = lambda: _session(
        str(tmp_path / "local.db"), campaign="on my laptop"
    )

    labels, hint = await _shown(tab)
    assert any("on my laptop" in label for label in labels)

    labels, hint = await _shown(tab, switches=1)
    assert labels == []
    assert "0 campaigns · the account" in hint


@pytest.mark.asyncio
async def test_switching_back_returns_to_the_first_store(
    account_config, tmp_path: Path
):
    tab = ResultsTab(account_config)
    tab.client = lambda: _session(str(tmp_path / "account.db"), campaign="in the cloud")
    tab.local_client = lambda: _session(
        str(tmp_path / "local.db"), campaign="on my laptop"
    )

    labels, _hint = await _shown(tab, switches=2)

    assert any("in the cloud" in label for label in labels)


@pytest.mark.asyncio
async def test_there_is_nothing_to_switch_to_without_an_account(tmp_path: Path):
    config = MagicMock(spec=CLIConfig)
    config.api_key = None
    config.base_url = "https://api.test.hackagent.dev"
    config.settings = MagicMock(db_path=":memory:")

    tab = ResultsTab(config)
    tab.client = MagicMock(name="account-session")
    tab.local_client = lambda: _session(
        str(tmp_path / "local.db"), campaign="on my laptop"
    )
    notes: list[str] = []
    tab.notify = lambda message, **_: notes.append(message)

    labels, hint = await _shown(tab, switches=1)

    assert any("on my laptop" in label for label in labels)
    assert "s:" not in hint
    assert notes and "no account is configured" in notes[0]


@pytest.mark.asyncio
async def test_the_key_reaches_the_view_with_the_tree_focused(
    account_config, tmp_path: Path
):
    """The tree takes the arrow keys; the store key must still get through."""
    tab = ResultsTab(account_config)
    tab.client = lambda: _session(str(tmp_path / "account.db"), campaign="in the cloud")
    tab.local_client = lambda: _session(
        str(tmp_path / "local.db"), campaign="on my laptop"
    )

    app = _Host(tab)
    async with app.run_test(size=(120, 24)) as pilot:
        await pilot.pause()
        tab.refresh_data()
        tab.query_one("#results-tree").focus()
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()
        labels, hint = _state(tab)

    assert any("on my laptop" in label for label in labels)
    assert "s: the account" in hint


@pytest.mark.asyncio
async def test_switching_to_a_store_that_fails_shows_nothing(
    account_config, tmp_path: Path
):
    """The runs on screen must never be credited to the store that failed."""

    def unreachable():
        raise OSError("Name or service not known")

    tab = ResultsTab(account_config)
    tab.client = unreachable
    tab.local_client = lambda: _session(
        str(tmp_path / "local.db"), campaign="on my laptop"
    )

    labels, _hint = await _shown(tab)
    assert any("on my laptop" in label for label in labels)

    labels, hint = await _shown(tab, switches=1)

    assert labels == []
    assert "Could not read results" in hint
    assert "s: this machine" in hint
