# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the `hackagent results` command group."""

from hackagent.core.settings import Settings
import unittest
from datetime import datetime
from enum import Enum
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from click.testing import CliRunner

from hackagent.interfaces.cli.commands import results as results_mod
from hackagent.interfaces.cli.commands.results import (
    _display_result_details,
    show,
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


class TestResultsShow(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.config = MagicMock()
        self.config.api_key = None
        self.config.base_url = None
        self.config.ca_bundle = None
        self.config.settings = Settings.resolve(
            api_key=self.config.api_key,
            backend="remote" if self.config.api_key else "local",
            base_url=self.config.base_url,
            db_path=":memory:",
            config_path="/nonexistent",
            env={},
        )

    def test_fetches_the_result_by_uuid_and_renders_details(self):
        result_id = uuid4()
        backend = MagicMock()
        backend.get_result.return_value = _result(
            id=result_id, agent_name="target-bot", attack_type="TAP"
        )

        with patch("hackagent.client._open_store", return_value=backend):
            outcome = self.runner.invoke(
                show, [str(result_id)], obj={"config": self.config}
            )

        self.assertEqual(outcome.exit_code, 0)
        backend.get_result.assert_called_once_with(result_id)
        self.assertIn("target-bot", outcome.output)

    def test_malformed_uuid_is_reported_as_a_fetch_failure(self):
        backend = MagicMock()

        with patch("hackagent.client._open_store", return_value=backend):
            outcome = self.runner.invoke(
                show, ["not-a-uuid"], obj={"config": self.config}
            )

        self.assertNotEqual(outcome.exit_code, 0)
        self.assertIn("Failed to fetch result", outcome.output)
        backend.get_result.assert_not_called()

    def test_backend_error_is_wrapped(self):
        backend = MagicMock()
        backend.get_result.side_effect = RuntimeError("database is locked")

        with patch("hackagent.client._open_store", return_value=backend):
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
        self.assertIn("Data", printed)

    def test_non_dict_data_is_stringified(self):
        printer = self._render(_result(data="raw blob"))

        printed = " ".join(str(call.args[0]) for call in printer.call_args_list[1:])
        self.assertIn("raw blob", printed)

    def test_falsy_data_is_skipped(self):
        printer = self._render(_result(data={}))

        self.assertEqual(printer.call_count, 1)


if __name__ == "__main__":
    unittest.main()
