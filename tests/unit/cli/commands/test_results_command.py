# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the `hackagent results` command group."""

import unittest
from datetime import datetime, timedelta
from enum import Enum
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from click.testing import CliRunner

from hackagent.cli.commands import results as results_mod
from hackagent.cli.commands.results import (
    _display_result_details,
    _display_result_summary,
    _generate_result_statistics,
    _show_logo_once,
    list as list_cmd,
    results as results_group,
    show,
    summary,
)


class _Status(Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


def _result(**fields):
    """Build a result object exposing exactly the given attributes."""
    fields.setdefault("id", uuid4())
    return SimpleNamespace(**fields)


def _page(items, total=None):
    return SimpleNamespace(items=list(items), total=total or len(items))


class TestShowLogoOnce(unittest.TestCase):
    def setUp(self):
        if hasattr(_show_logo_once, "_shown"):
            del _show_logo_once._shown
        self.addCleanup(
            lambda: (
                hasattr(_show_logo_once, "_shown")
                and delattr(_show_logo_once, "_shown")
            )
        )

    def test_splash_is_displayed_only_on_the_first_call(self):
        with patch("hackagent.cli.banner.display_hackagent_splash") as splash:
            _show_logo_once()
            _show_logo_once()
            _show_logo_once()

        splash.assert_called_once_with()

    def test_group_invocation_shows_the_logo(self):
        with (
            patch("hackagent.cli.banner.display_hackagent_splash") as splash,
            patch.object(results_mod, "launch_tui"),
        ):
            result = CliRunner().invoke(
                results_group, ["list"], obj={"config": MagicMock()}
            )

        self.assertEqual(result.exit_code, 0)
        splash.assert_called_once_with()


class TestResultsList(unittest.TestCase):
    def test_list_validates_config_and_opens_the_results_tab(self):
        config = MagicMock()

        with patch.object(results_mod, "launch_tui") as launch:
            result = CliRunner().invoke(list_cmd, [], obj={"config": config})

        self.assertEqual(result.exit_code, 0)
        config.validate.assert_called_once_with()
        launch.assert_called_once_with(config, initial_tab="results")

    def test_invalid_config_is_reported_as_a_click_exception(self):
        config = MagicMock()
        config.validate.side_effect = ValueError("API key is required")

        with patch.object(results_mod, "launch_tui") as launch:
            result = CliRunner().invoke(list_cmd, [], obj={"config": config})

        self.assertNotEqual(result.exit_code, 0)
        launch.assert_not_called()
        self.assertIn("API key is required", result.output)

    def test_filter_options_are_accepted(self):
        config = MagicMock()

        with patch.object(results_mod, "launch_tui"):
            result = CliRunner().invoke(
                list_cmd,
                [
                    "--limit",
                    "5",
                    "--status",
                    "completed",
                    "--agent",
                    "bot",
                    "--attack-type",
                    "tap",
                ],
                obj={"config": config},
            )

        self.assertEqual(result.exit_code, 0)

    def test_unknown_status_choice_is_rejected(self):
        result = CliRunner().invoke(
            list_cmd, ["--status", "exploded"], obj={"config": MagicMock()}
        )

        self.assertEqual(result.exit_code, 2)


class TestResultsShow(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.config = MagicMock()

    def test_fetches_the_result_by_uuid_and_renders_details(self):
        result_id = uuid4()
        backend = MagicMock()
        backend.get_result.return_value = _result(
            id=result_id, agent_name="target-bot", attack_type="TAP"
        )

        with patch("hackagent.storage.local.LocalBackend", return_value=backend):
            outcome = self.runner.invoke(
                show, [str(result_id)], obj={"config": self.config}
            )

        self.assertEqual(outcome.exit_code, 0)
        backend.get_result.assert_called_once_with(result_id)
        self.assertIn("target-bot", outcome.output)

    def test_malformed_uuid_is_reported_as_a_fetch_failure(self):
        backend = MagicMock()

        with patch("hackagent.storage.local.LocalBackend", return_value=backend):
            outcome = self.runner.invoke(
                show, ["not-a-uuid"], obj={"config": self.config}
            )

        self.assertNotEqual(outcome.exit_code, 0)
        self.assertIn("Failed to fetch result", outcome.output)
        backend.get_result.assert_not_called()

    def test_backend_error_is_wrapped(self):
        backend = MagicMock()
        backend.get_result.side_effect = RuntimeError("database is locked")

        with patch("hackagent.storage.local.LocalBackend", return_value=backend):
            outcome = self.runner.invoke(
                show, [str(uuid4())], obj={"config": self.config}
            )

        self.assertNotEqual(outcome.exit_code, 0)
        self.assertIn("database is locked", outcome.output)


class TestDisplayResultDetails(unittest.TestCase):
    def _render(self, result):
        with patch.object(results_mod.console, "print") as printer:
            _display_result_details(result)
        return printer

    def test_minimal_result_renders_only_the_id_row(self):
        result_id = uuid4()
        printer = self._render(SimpleNamespace(id=result_id))

        table = printer.call_args_list[0].args[0]
        self.assertEqual(len(table.columns[0]._cells), 1)
        self.assertEqual(table.columns[1]._cells[0], str(result_id))

    def test_enum_status_is_unwrapped_to_its_value(self):
        printer = self._render(_result(evaluation_status=_Status.COMPLETED))

        table = printer.call_args_list[0].args[0]
        self.assertIn("COMPLETED", table.columns[1]._cells)

    def test_plain_status_is_stringified(self):
        printer = self._render(_result(evaluation_status="running"))

        table = printer.call_args_list[0].args[0]
        self.assertIn("running", table.columns[1]._cells)

    def test_datetime_created_at_is_formatted(self):
        printer = self._render(_result(created_at=datetime(2026, 1, 2, 3, 4, 5)))

        table = printer.call_args_list[0].args[0]
        self.assertIn("2026-01-02 03:04:05", table.columns[1]._cells)

    def test_string_created_at_is_passed_through(self):
        printer = self._render(_result(created_at="2026-01-02T03:04:05Z"))

        table = printer.call_args_list[0].args[0]
        self.assertIn("2026-01-02T03:04:05Z", table.columns[1]._cells)

    def test_empty_created_at_adds_no_row(self):
        printer = self._render(_result(created_at=None))

        table = printer.call_args_list[0].args[0]
        self.assertEqual(len(table.columns[0]._cells), 1)

    def test_dict_data_is_pretty_printed_as_json(self):
        printer = self._render(_result(data={"asr": 0.5, "n": 2}))

        printed = " ".join(str(call.args[0]) for call in printer.call_args_list[1:])
        self.assertIn('"asr": 0.5', printed)
        self.assertIn("Result Data", printed)

    def test_non_dict_data_is_stringified(self):
        printer = self._render(_result(data="raw blob"))

        printed = " ".join(str(call.args[0]) for call in printer.call_args_list[1:])
        self.assertIn("raw blob", printed)

    def test_falsy_data_is_skipped(self):
        printer = self._render(_result(data={}))

        self.assertEqual(printer.call_count, 1)


class TestGenerateResultStatistics(unittest.TestCase):
    def test_counts_statuses_agents_and_attack_types(self):
        results = [
            _result(
                evaluation_status=_Status.COMPLETED,
                agent_name="bot-a",
                attack_type="TAP",
            ),
            _result(
                evaluation_status=_Status.COMPLETED,
                agent_name="bot-a",
                attack_type="PAIR",
            ),
            _result(evaluation_status="FAILED", agent_name="bot-b", attack_type="TAP"),
        ]

        stats = _generate_result_statistics(results, days=7)

        self.assertEqual(stats["total_results"], 3)
        self.assertEqual(stats["status_breakdown"], {"COMPLETED": 2, "FAILED": 1})
        self.assertEqual(stats["agent_breakdown"], {"bot-a": 2, "bot-b": 1})
        self.assertEqual(stats["attack_type_breakdown"], {"TAP": 2, "PAIR": 1})
        self.assertEqual(stats["period_days"], 7)

    def test_metrics_are_averaged_over_results_carrying_data(self):
        results = [
            _result(
                data={"overall_majority_vote_asr": 1.0, "overall_fleiss_kappa": 0.4}
            ),
            _result(
                data={"overall_majority_vote_asr": 0.0, "overall_fleiss_kappa": 0.8}
            ),
        ]

        stats = _generate_result_statistics(results, days=1)

        self.assertAlmostEqual(stats["avg_majority_vote_asr"], 0.5)
        self.assertAlmostEqual(stats["avg_fleiss_kappa"], 0.6)

    def test_missing_metrics_average_to_zero(self):
        stats = _generate_result_statistics([_result(agent_name="a")], days=1)

        self.assertEqual(stats["avg_majority_vote_asr"], 0.0)
        self.assertEqual(stats["avg_fleiss_kappa"], 0.0)

    def test_empty_input_produces_empty_breakdowns(self):
        stats = _generate_result_statistics([], days=30)

        self.assertEqual(stats["total_results"], 0)
        self.assertEqual(stats["status_breakdown"], {})
        self.assertEqual(stats["agent_breakdown"], {})
        self.assertEqual(stats["attack_type_breakdown"], {})
        self.assertIn("generated_at", stats)


class TestDisplayResultSummary(unittest.TestCase):
    def _render(self, stats):
        with patch.object(results_mod.console, "print") as printer:
            _display_result_summary(stats)
        return printer

    def _stats(self, **overrides):
        base = {
            "period_days": 7,
            "total_results": 0,
            "status_breakdown": {},
            "agent_breakdown": {},
            "attack_type_breakdown": {},
            "avg_majority_vote_asr": 0.0,
            "avg_fleiss_kappa": 0.0,
            "generated_at": "now",
        }
        base.update(overrides)
        return base

    def test_empty_stats_still_render_the_metrics_table(self):
        printer = self._render(self._stats())

        printed = [call.args[0] for call in printer.call_args_list]
        tables = [item for item in printed if hasattr(item, "columns")]
        self.assertEqual(len(tables), 1)
        self.assertIn("Majority Vote ASR", tables[0].columns[0]._cells)

    def test_status_percentages_are_computed(self):
        printer = self._render(
            self._stats(total_results=4, status_breakdown={"COMPLETED": 3, "FAILED": 1})
        )

        tables = [
            call.args[0]
            for call in printer.call_args_list
            if hasattr(call.args[0], "columns")
        ]
        self.assertIn("75.0%", tables[0].columns[2]._cells)
        self.assertIn("25.0%", tables[0].columns[2]._cells)

    def test_agents_are_sorted_and_capped_at_five(self):
        breakdown = {f"bot-{i}": i for i in range(1, 8)}
        printer = self._render(self._stats(total_results=28, agent_breakdown=breakdown))

        tables = [
            call.args[0]
            for call in printer.call_args_list
            if hasattr(call.args[0], "columns")
        ]
        agent_table = tables[0]
        self.assertEqual(
            agent_table.columns[0]._cells, ["bot-7", "bot-6", "bot-5", "bot-4", "bot-3"]
        )

    def test_attack_type_table_is_rendered(self):
        printer = self._render(
            self._stats(total_results=2, attack_type_breakdown={"TAP": 2})
        )

        tables = [
            call.args[0]
            for call in printer.call_args_list
            if hasattr(call.args[0], "columns")
        ]
        self.assertIn("TAP", tables[0].columns[0]._cells)

    def test_metric_averages_are_rendered_with_three_decimals(self):
        printer = self._render(
            self._stats(avg_majority_vote_asr=0.12345, avg_fleiss_kappa=0.6789)
        )

        tables = [
            call.args[0]
            for call in printer.call_args_list
            if hasattr(call.args[0], "columns")
        ]
        self.assertEqual(tables[-1].columns[1]._cells, ["0.123", "0.679"])


class TestResultsSummaryCommand(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.config = MagicMock()

    def _invoke(self, pages, args=()):
        backend = MagicMock()
        backend.list_results.side_effect = pages
        with (
            patch("hackagent.storage.local.LocalBackend", return_value=backend),
            patch.object(results_mod, "_display_result_summary") as display,
        ):
            outcome = self.runner.invoke(
                summary, list(args), obj={"config": self.config}
            )
        return outcome, backend, display

    def test_summary_pages_through_every_result(self):
        recent = datetime.now()
        pages = [
            _page([_result(created_at=recent) for _ in range(2)], total=3),
            _page([_result(created_at=recent)], total=3),
        ]

        outcome, backend, display = self._invoke(pages)

        self.assertEqual(outcome.exit_code, 0)
        self.assertEqual(backend.list_results.call_count, 2)
        self.assertEqual(
            backend.list_results.call_args_list[1].kwargs, {"page": 2, "page_size": 200}
        )
        self.assertEqual(display.call_args.args[0]["total_results"], 3)

    def test_results_older_than_the_window_are_dropped(self):
        pages = [
            _page(
                [
                    _result(created_at=datetime.now()),
                    _result(created_at=datetime.now() - timedelta(days=40)),
                ]
            )
        ]

        outcome, _, display = self._invoke(pages, args=["--days", "7"])

        self.assertEqual(outcome.exit_code, 0)
        self.assertEqual(display.call_args.args[0]["total_results"], 1)
        self.assertEqual(display.call_args.args[0]["period_days"], 7)

    def test_iso_string_dates_are_parsed(self):
        recent = (datetime.now() - timedelta(days=1)).isoformat()
        old = (datetime.now() - timedelta(days=99)).isoformat()
        pages = [_page([_result(created_at=recent), _result(created_at=old)])]

        _, _, display = self._invoke(pages, args=["--days", "7"])

        self.assertEqual(display.call_args.args[0]["total_results"], 1)

    def test_unparseable_and_missing_dates_are_kept(self):
        pages = [
            _page([_result(created_at="not-a-date"), _result(agent_name="dateless")])
        ]

        _, _, display = self._invoke(pages)

        self.assertEqual(display.call_args.args[0]["total_results"], 2)

    def test_status_filter_matches_case_insensitively(self):
        pages = [
            _page(
                [
                    _result(evaluation_status=_Status.COMPLETED),
                    _result(evaluation_status=_Status.FAILED),
                ]
            )
        ]

        _, _, display = self._invoke(pages, args=["--status", "completed"])

        self.assertEqual(
            display.call_args.args[0]["status_breakdown"], {"COMPLETED": 1}
        )

    def test_agent_and_attack_type_filters_are_substring_matches(self):
        pages = [
            _page(
                [
                    _result(agent_name="Prod-Bot", attack_type="TAP"),
                    _result(agent_name="Staging-Bot", attack_type="PAIR"),
                ]
            )
        ]

        _, _, display = self._invoke(
            pages, args=["--agent", "prod", "--attack-type", "ta"]
        )

        self.assertEqual(display.call_args.args[0]["agent_breakdown"], {"Prod-Bot": 1})

    def test_backend_failure_is_wrapped_in_a_click_exception(self):
        backend = MagicMock()
        backend.list_results.side_effect = RuntimeError("no such table: results")

        with patch("hackagent.storage.local.LocalBackend", return_value=backend):
            outcome = self.runner.invoke(summary, [], obj={"config": self.config})

        self.assertNotEqual(outcome.exit_code, 0)
        self.assertIn("Failed to generate summary", outcome.output)

    def test_invalid_config_short_circuits_the_summary(self):
        self.config.validate.side_effect = ValueError("Base URL is required")

        with patch("hackagent.storage.local.LocalBackend") as backend_cls:
            outcome = self.runner.invoke(summary, [], obj={"config": self.config})

        self.assertNotEqual(outcome.exit_code, 0)
        backend_cls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
