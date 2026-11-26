# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""What the welcome screen's menu opens, besides the builder and results:
the dataset presets, the setup, the dashboard and the queued runs. Each says
what the command line says for the same thing, from the same place."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from click.testing import CliRunner
from rich.text import Text
from textual.widgets import OptionList, Static

from hackagent.interfaces.cli.config import CLIConfig
from hackagent.interfaces.tui.app import HackAgentTUI
from hackagent.interfaces.tui.views.campaign.welcome import WelcomeScreen
from hackagent.interfaces.tui.views.home import (
    DashboardScreen,
    DatasetsScreen,
    QueuedRunsScreen,
    SettingsScreen,
)

WIDE = (120, 40)


@pytest.fixture
def cli_config():
    config = MagicMock(spec=CLIConfig)
    config.api_key = "test-key"
    config.base_url = "https://api.test.hackagent.dev"
    config.settings = MagicMock(name="resolved-settings")
    return config


def _plain(screen, selector: str) -> str:
    return Text.from_markup(str(screen.query_one(selector, Static).content)).plain


async def _open(app, pilot, entry: str):
    """Choose ``entry`` on the welcome screen's menu."""
    await pilot.pause()
    assert isinstance(app.screen, WelcomeScreen)
    app.screen.dismiss(entry)
    await pilot.pause()


def _editor(screen, key: str):
    """The editor of a form's row for ``key``, as in the builder."""
    return screen.rows()[key].query_one(".value")


async def _settle(app, pilot) -> None:
    await app.workers.wait_for_complete()
    await pilot.pause()


# -- datasets -------------------------------------------------------------


@pytest.mark.asyncio
async def test_datasets_lists_the_presets_as_the_cli_does(cli_config):
    from hackagent.client import presets
    from hackagent.interfaces.cli.commands.datasets import datasets
    from hackagent.interfaces.datasets import preset_rows

    app = HackAgentTUI(cli_config)
    async with app.run_test(size=WIDE) as pilot:
        await _open(app, pilot, "datasets")
        assert isinstance(app.screen, DatasetsScreen)
        listing = app.screen.query_one(OptionList)
        names = [listing.get_option_at_index(i).id for i in range(listing.option_count)]
        about = _plain(app.screen, "#details")

    rows = preset_rows(presets())
    assert names == [name for name, _ in rows]
    # One line each: what a preset is is said beside the list, not in it.
    assert all("\n" not in row.plain for _, row in rows)
    description = str(presets()[names[0]]["description"])
    assert description in about
    # The highlighted preset, and how a campaign names it.
    assert names[0] in about and "type: preset" in about
    # The command line lists the same rows.
    printed = CliRunner().invoke(datasets, ["list"]).output
    for name, row in rows:
        assert row.plain.split("\n")[0] in printed


@pytest.mark.asyncio
async def test_sample_loads_some_goals_of_the_highlighted_preset(cli_config):
    app = HackAgentTUI(cli_config)
    with patch(
        "hackagent.client.load_goals", return_value=["goal one", "goal two"]
    ) as load:
        async with app.run_test(size=WIDE) as pilot:
            await _open(app, pilot, "datasets")
            await pilot.press("enter")
            await _settle(app, pilot)
            about = _plain(app.screen, "#details")

    assert load.call_args.kwargs["limit"] == 5
    assert "1. goal one" in about and "2. goal two" in about


# -- settings ---------------------------------------------------------------


def test_doctor_prints_the_report_the_setup_screen_shows(tmp_path, monkeypatch):
    from hackagent.interfaces.cli.main import cli
    from hackagent.interfaces.setup import report_markup, setup_report

    monkeypatch.setenv("HACKAGENT_DB_PATH", str(tmp_path / "db.sqlite"))
    config_file = str(tmp_path / "config.json")
    printed = CliRunner().invoke(cli, ["--config-file", config_file, "doctor"])

    assert printed.exit_code == 0, printed.output
    expected = report_markup(*setup_report(CLIConfig(config_file=config_file)))
    lines = [Text.from_markup(line).plain for line in expected]
    # Whitespace aside: a long path wraps at the terminal's edge.
    assert "".join(printed.output.split()) == "".join("".join(lines).split())
    assert "! No local database yet" in printed.output


@pytest.mark.asyncio
async def test_settings_show_the_checks(cli_config):
    from hackagent.interfaces.setup import Check, Section

    cli_config.backend, cli_config.base_url = "local", "https://api.test"
    cli_config.ca_bundle, cli_config.verbose = None, 1
    report = (
        (Section("Dependencies", (Check("failed", "pandas not found"),)),),
        Check("warning", "1 issue to address", fix=("Set up again", "hackagent init")),
    )
    app = HackAgentTUI(cli_config)
    with patch("hackagent.interfaces.setup.setup_report", return_value=report):
        async with app.run_test(size=WIDE) as pilot:
            await _open(app, pilot, "settings")
            assert isinstance(app.screen, SettingsScreen)
            await _settle(app, pilot)
            shown = _plain(app.screen, "#said")

    assert "✗ pandas not found" in shown
    assert "! 1 issue to address" in shown


@pytest.mark.asyncio
async def test_settings_save_what_changed_as_config_set_does(cli_config):
    from hackagent.interfaces.setup import Check

    cli_config.backend, cli_config.base_url = "local", "https://api.test"
    cli_config.ca_bundle, cli_config.verbose = None, 1
    app = HackAgentTUI(cli_config)
    with patch(
        "hackagent.interfaces.setup.setup_report",
        return_value=((), Check("passed", "Ready to use HackAgent")),
    ):
        async with app.run_test(size=WIDE) as pilot:
            await _open(app, pilot, "settings")
            # The builder's rows: the key, the value, whether it is edited.
            _editor(app.screen, "backend").value = "remote"
            _editor(app.screen, "verbose").value = "3"
            await pilot.pause()
            assert "edited" in str(app.screen.rows()["backend"]._state.content)
            await pilot.press("ctrl+s")
            await _settle(app, pilot)

    # Only what changed, then saved once, as ``hackagent config set`` does.
    assert [call.args for call in cli_config.set_user_override.call_args_list] == [
        ("backend", "remote"),
        ("verbose", 3),
    ]
    cli_config.save.assert_called_once()


@pytest.mark.asyncio
async def test_a_log_level_saved_applies_to_the_open_app(cli_config, monkeypatch):
    """Saved, it is what the next run in this app logs from, not only the
    next time hackagent starts."""
    from hackagent.interfaces.cli.logging_setup import shown_level
    from hackagent.interfaces.setup import Check

    monkeypatch.delenv("HACKAGENT_LOG_LEVEL", raising=False)
    cli_handler = logging.NullHandler(logging.WARNING)
    cli_handler.hackagent_cli = True
    package = logging.getLogger("hackagent")
    monkeypatch.setattr(package, "handlers", [cli_handler])
    monkeypatch.setattr(package, "level", logging.DEBUG)
    cli_config.backend, cli_config.base_url = "local", "https://api.test"
    cli_config.ca_bundle, cli_config.verbose = None, 1

    def saved_level(key, value):
        setattr(cli_config, key, value)

    cli_config.set_user_override.side_effect = saved_level
    app = HackAgentTUI(cli_config)
    with patch(
        "hackagent.interfaces.setup.setup_report",
        return_value=((), Check("passed", "Ready to use HackAgent")),
    ):
        async with app.run_test(size=WIDE) as pilot:
            await _open(app, pilot, "settings")
            _editor(app.screen, "verbose").value = "3"
            await pilot.pause()
            await pilot.press("ctrl+s")
            await _settle(app, pilot)

    assert shown_level() == logging.DEBUG


# -- dashboard ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_dashboard_is_served_with_the_options_of_hackagent_web(
    cli_config,
):
    dashboard = SimpleNamespace(
        url="http://127.0.0.1:8080",
        session=SimpleNamespace(settings=SimpleNamespace(mode=None)),
        app=None,
        db_path="/tmp/other.db",
    )
    served = MagicMock(dashboard=dashboard)
    app = HackAgentTUI(cli_config)
    with (
        patch("hackagent.interfaces.dashboard.in_use", return_value=False),
        patch(
            "hackagent.interfaces.dashboard.open_dashboard", return_value=dashboard
        ) as opened,
        patch("hackagent.interfaces.dashboard.Served", return_value=served) as serve,
        patch(
            "hackagent.interfaces.dashboard.about",
            return_value=[("database", "/tmp/other.db")],
        ),
        patch("webbrowser.open", return_value=True) as browser,
    ):
        async with app.run_test(size=WIDE) as pilot:
            await _open(app, pilot, "dashboard")
            assert isinstance(app.screen, DashboardScreen)
            _editor(app.screen, "port").value = "8080"
            _editor(app.screen, "db-path").value = "/tmp/other.db"
            _editor(app.screen, "local").value = True
            await pilot.pause()
            await pilot.press("ctrl+r")
            await pilot.pause()
            shown = _plain(app.screen, "#said")
            assert "Serving at http://127.0.0.1:8080" in shown

            # Leaving the screen keeps it served, and the menu says where.
            await pilot.press("escape")
            await pilot.pause()
            assert app.dashboard is served
            menu = app.screen.query_one("#menu", OptionList)
            entries = " ".join(
                str(menu.get_option_at_index(i).prompt)
                for i in range(menu.option_count)
            )
            assert "Serving at http://127.0.0.1:8080" in entries
            served.stop.assert_not_called()

    assert opened.call_args.kwargs == {
        "host": "127.0.0.1",
        "port": 8080,
        "db_path": "/tmp/other.db",
        "force_local": True,
    }
    assert serve.call_args.args[1:] == ("127.0.0.1", 8080)
    browser.assert_called_once_with("http://127.0.0.1:8080")
    # Leaving the app stops it.
    served.stop.assert_called_once()


@pytest.mark.asyncio
async def test_a_dashboard_without_its_extra_says_how_to_install_it(cli_config):
    app = HackAgentTUI(cli_config)
    with (
        patch("hackagent.interfaces.dashboard.in_use", return_value=False),
        patch(
            "hackagent.interfaces.dashboard.open_dashboard",
            side_effect=ImportError("No module named 'flask'"),
        ),
    ):
        async with app.run_test(size=WIDE) as pilot:
            await _open(app, pilot, "dashboard")
            await pilot.press("ctrl+r")
            await pilot.pause()
            shown = _plain(app.screen, "#said")

    assert "✗ The dashboard needs its dependencies" in shown
    assert "pip install 'hackagent[web]'" in shown


# -- queued runs --------------------------------------------------------------


@pytest.mark.asyncio
async def test_queued_runs_need_the_api_key(cli_config):
    cli_config.settings = SimpleNamespace(api_key=None)
    app = HackAgentTUI(cli_config)
    async with app.run_test(size=WIDE) as pilot:
        await _open(app, pilot, "queued")
        assert isinstance(app.screen, QueuedRunsScreen)
        await _settle(app, pilot)
        shown = _plain(app.screen, "#said")

    assert "export HACKAGENT_API_KEY" in shown


def _store(*runs):
    store = MagicMock()
    store.list_queued_local_runs.return_value = list(runs)
    return store


@pytest.mark.asyncio
async def test_a_queued_run_is_refused_as_hackagent_run_refuses_it(cli_config):
    from hackagent.interfaces import queued

    run_id = str(uuid4())
    cli_config.settings = SimpleNamespace(api_key="k", dashboard_url=None)
    refused = queued.Refused(
        "Set these variables with your model keys, then run again:",
        missing=("OPENAI_KEY",),
    )
    app = HackAgentTUI(cli_config)
    with (
        patch.object(
            queued,
            "connect",
            return_value=_store(
                {"id": run_id, "agent_name": "bot", "timestamp": "2026-11-26T10:00"}
            ),
        ),
        patch.object(queued, "prepare", side_effect=refused),
        patch.object(queued, "execute") as execute,
    ):
        async with app.run_test(size=WIDE) as pilot:
            await _open(app, pilot, "queued")
            await _settle(app, pilot)
            listing = app.screen.query_one(OptionList)
            assert listing.get_option_at_index(0).id == run_id
            await pilot.press("enter")
            await _settle(app, pilot)
            shown = _plain(app.screen, "#said")

    assert "✗ Set these variables" in shown and "export OPENAI_KEY=..." in shown
    execute.assert_not_called()


@pytest.mark.asyncio
async def test_a_queued_run_runs_here_with_its_log_on_the_run_view(
    cli_config, monkeypatch
):
    from hackagent.interfaces import queued
    from hackagent.interfaces.tui.views.campaign.screens import RunScreen

    # The package logger open, as the CLI opens it before the app starts.
    monkeypatch.setattr(logging.getLogger("hackagent"), "level", logging.DEBUG)
    monkeypatch.setattr(logging.root.manager, "disable", logging.NOTSET)
    run_id = uuid4()
    cli_config.settings = SimpleNamespace(api_key="k", dashboard_url=None)
    ready = queued.Ready(
        run_id, SimpleNamespace(campaign=SimpleNamespace(name="queued demo"))
    )

    def execute(store, ready, settings):
        logging.getLogger("hackagent.campaign").info("campaign queued demo · started")
        return SimpleNamespace(status="COMPLETED", note="")

    app = HackAgentTUI(cli_config)
    with (
        patch.object(
            queued,
            "connect",
            return_value=_store(
                {"id": str(run_id), "agent_name": "bot", "timestamp": "2026"}
            ),
        ),
        patch.object(queued, "prepare", return_value=ready),
        patch.object(queued, "execute", side_effect=execute),
    ):
        async with app.run_test(size=WIDE) as pilot:
            await _open(app, pilot, "queued")
            await _settle(app, pilot)
            await pilot.press("enter")
            await _settle(app, pilot)
            await pilot.pause(0.3)
            assert isinstance(app.screen, RunScreen)
            feed = app.screen_stack[-2]._feed
            lines = [Text.from_markup(line).plain for line in feed.lines]

    assert any("campaign queued demo · started" in line for line in lines)
    assert any("run · completed" in line for line in lines)


@pytest.mark.asyncio
async def test_a_port_in_use_is_said_on_its_row_as_the_builder_says_a_problem(
    cli_config,
):
    app = HackAgentTUI(cli_config)
    with (
        patch("hackagent.interfaces.dashboard.in_use", return_value=True),
        patch("hackagent.interfaces.dashboard.open_dashboard") as opened,
    ):
        async with app.run_test(size=WIDE) as pilot:
            await _open(app, pilot, "dashboard")
            await pilot.press("ctrl+r")
            await pilot.pause()
            row = app.screen.rows()["port"]

    assert row.has_class("-error")
    assert row.issue.startswith("in use already")
    opened.assert_not_called()
