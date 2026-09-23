# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for results CLI helpers and commands."""

import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from click.testing import CliRunner

from hackagent.cli.commands.results import (
    _display_result_details,
    _generate_result_statistics,
    results,
)
from hackagent.core.contracts import EvalStatus


def _config():
    cfg = MagicMock()
    cfg.validate.return_value = None
    return cfg


def _result(**overrides):
    data = {
        "id": uuid4(),
        "agent_name": "weather-bot",
        "attack_type": "pair",
        "evaluation_status": EvalStatus.SUCCESSFUL_JAILBREAK,
        "created_at": datetime(2026, 1, 2, 3, 4, 5),
        "data": {"overall_majority_vote_asr": 0.8, "overall_fleiss_kappa": 0.4},
    }
    data.update(overrides)
    return SimpleNamespace(**data)


class TestGenerateResultStatistics(unittest.TestCase):
    def test_empty_results(self):
        stats = _generate_result_statistics([], days=7)
        self.assertEqual(stats["total_results"], 0)
        self.assertEqual(stats["avg_majority_vote_asr"], 0.0)
        self.assertEqual(stats["avg_fleiss_kappa"], 0.0)
        self.assertEqual(stats["period_days"], 7)

    def test_aggregates_status_agent_attack_and_metrics(self):
        results_list = [
            _result(),
            _result(
                agent_name="other-bot",
                attack_type="tap",
                evaluation_status="FAILED_JAILBREAK",
                data={"overall_majority_vote_asr": 0.2, "overall_fleiss_kappa": 0.0},
            ),
            _result(
                evaluation_status=SimpleNamespace(value="NOT_EVALUATED"),
                data=None,
            ),
        ]
        stats = _generate_result_statistics(results_list, days=3)
        self.assertEqual(stats["total_results"], 3)
        self.assertEqual(stats["status_breakdown"]["SUCCESSFUL_JAILBREAK"], 1)
        self.assertEqual(stats["status_breakdown"]["FAILED_JAILBREAK"], 1)
        self.assertEqual(stats["status_breakdown"]["NOT_EVALUATED"], 1)
        self.assertEqual(stats["agent_breakdown"]["weather-bot"], 2)
        self.assertEqual(stats["attack_type_breakdown"]["pair"], 2)
        self.assertAlmostEqual(stats["avg_majority_vote_asr"], 0.5)
        self.assertAlmostEqual(stats["avg_fleiss_kappa"], 0.2)


class TestDisplayResultDetails(unittest.TestCase):
    def test_renders_enum_status_datetime_and_json_data(self):
        from io import StringIO

        from rich.console import Console

        result = _result()
        buffer = StringIO()
        console = Console(file=buffer, width=120, force_terminal=True)
        with patch("hackagent.cli.commands.results.console", console):
            _display_result_details(result)
        printed = buffer.getvalue()
        self.assertIn(str(result.id), printed)
        self.assertIn("weather-bot", printed)
        self.assertIn("SUCCESSFUL_JAILBREAK", printed)
        self.assertIn("2026-01-02 03:04:05", printed)
        self.assertIn("overall_majority_vote_asr", printed)

    def test_non_dict_data_is_stringified(self):
        result = _result(data="plain-notes")
        with patch("hackagent.cli.commands.results.console") as console:
            _display_result_details(result)
        printed = " ".join(str(call) for call in console.print.call_args_list)
        self.assertIn("plain-notes", printed)


class TestResultsCommands(unittest.TestCase):
    def test_list_launches_results_tui(self):
        runner = CliRunner()
        with (
            patch("hackagent.cli.commands.results._show_logo_once"),
            patch("hackagent.cli.commands.results.launch_tui") as mock_tui,
        ):
            result = runner.invoke(
                results, ["list", "--limit", "5"], obj={"config": _config()}
            )
        self.assertEqual(result.exit_code, 0, result.output)
        mock_tui.assert_called_once()
        self.assertEqual(mock_tui.call_args.kwargs["initial_tab"], "results")

    def test_show_fetches_and_renders_a_result(self):
        runner = CliRunner()
        result_id = uuid4()
        record = _result(id=result_id)
        backend = MagicMock()
        backend.get_result.return_value = record
        with (
            patch("hackagent.cli.commands.results._show_logo_once"),
            patch("hackagent.server.storage.local.LocalBackend", return_value=backend),
        ):
            result = runner.invoke(
                results, ["show", str(result_id)], obj={"config": _config()}
            )
        self.assertEqual(result.exit_code, 0, result.output)
        backend.get_result.assert_called_once()
        self.assertIn("weather-bot", result.output)

    def test_show_wraps_backend_errors(self):
        runner = CliRunner()
        backend = MagicMock()
        backend.get_result.side_effect = RuntimeError("missing")
        with (
            patch("hackagent.cli.commands.results._show_logo_once"),
            patch("hackagent.server.storage.local.LocalBackend", return_value=backend),
        ):
            result = runner.invoke(
                results, ["show", str(uuid4())], obj={"config": _config()}
            )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Failed to fetch result", result.output)

    def test_summary_filters_by_agent_and_days(self):
        runner = CliRunner()
        now = datetime.now()
        page = SimpleNamespace(
            items=[
                _result(created_at=now, agent_name="keep-me"),
                _result(
                    created_at=now - timedelta(days=30),
                    agent_name="keep-me",
                    attack_type="tap",
                ),
                _result(created_at=now, agent_name="skip-me"),
            ],
            total=3,
        )
        backend = MagicMock()
        backend.list_results.return_value = page
        with (
            patch("hackagent.cli.commands.results._show_logo_once"),
            patch("hackagent.server.storage.local.LocalBackend", return_value=backend),
        ):
            result = runner.invoke(
                results,
                ["summary", "--days", "7", "--agent", "keep"],
                obj={"config": _config()},
            )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Total Results: 1", result.output)
        self.assertIn("keep-me", result.output)
        self.assertNotIn("skip-me", result.output)


if __name__ == "__main__":
    unittest.main()
