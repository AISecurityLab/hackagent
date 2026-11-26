# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the `hackagent results` command group."""

from hackagent.core.settings import Settings
import unittest
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from click.testing import CliRunner

from hackagent.core.contracts import EvalStatus
from hackagent.interfaces.cli.commands import results as results_mod
from hackagent.interfaces.cli.commands.results import (
    _display_result_details,
    show,
)
from hackagent.storage.records import ResultRecord


def _result(**fields):
    """A result as both backends return it."""
    when = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    record = {
        "id": uuid4(),
        "run_id": uuid4(),
        "goal": "Explain how to pick a lock",
        "goal_index": 0,
        "evaluation_status": EvalStatus.SUCCESSFUL_JAILBREAK.value,
        "evaluation_notes": None,
        "evaluation_metrics": {},
        "metadata": {},
        "created_at": when,
        "updated_at": when,
    }
    record.update(fields)
    return ResultRecord(**record)


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
            id=result_id, goal="Explain how to pick a lock"
        )

        with patch("hackagent.client._open_store", return_value=backend):
            outcome = self.runner.invoke(
                show, [str(result_id)], obj={"config": self.config}
            )

        self.assertEqual(outcome.exit_code, 0)
        backend.get_result.assert_called_once_with(result_id)
        self.assertIn("Explain how to pick a lock", outcome.output)
        self.assertIn("jailbroken", outcome.output)

    def test_json_prints_every_field_and_the_verdict(self):
        result_id = uuid4()
        backend = MagicMock()
        backend.get_result.return_value = _result(
            id=result_id, metadata={"response": "Sure, first..."}
        )

        with patch("hackagent.client._open_store", return_value=backend):
            outcome = self.runner.invoke(
                show, [str(result_id), "--json"], obj={"config": self.config}
            )

        self.assertEqual(outcome.exit_code, 0, outcome.output)
        printed = json.loads(outcome.stdout)
        self.assertEqual(printed["id"], str(result_id))
        self.assertEqual(printed["verdict"], "jailbroken")
        self.assertEqual(printed["metadata"]["response"], "Sure, first...")
        backend.get_run.assert_not_called()

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
    def _printed(self, result):
        with patch.object(results_mod.console, "print") as printer:
            _display_result_details(result)
        table = printer.call_args_list[0].args[0]
        rows = dict(zip(table.columns[0]._cells, table.columns[1]._cells))
        rest = [str(call.args[0]) for call in printer.call_args_list[1:]]
        return rows, rest

    def test_the_table_names_the_result_its_run_and_its_verdict(self):
        result = _result()
        rows, _ = self._printed(result)
        self.assertEqual(rows["ID"], str(result.id))
        self.assertEqual(rows["Run"], str(result.run_id))
        self.assertEqual(rows["Verdict"], "jailbroken")
        self.assertEqual(rows["Recorded"], "2026-01-02 03:04:05")

    def test_the_goal_and_the_reply_follow_the_table(self):
        _, rest = self._printed(
            _result(goal="the goal", metadata={"response": "the reply"})
        )
        self.assertIn("the goal", rest)
        self.assertIn("the reply", rest)

    def test_the_judges_notes_are_shown_when_there_are_any(self):
        _, with_notes = self._printed(_result(evaluation_notes="refused politely"))
        _, without = self._printed(_result(evaluation_notes=None))
        self.assertIn("refused politely", with_notes)
        self.assertNotIn("\n[heading]Judges' notes[/heading]", without)

    def test_a_result_without_a_reply_says_so(self):
        _, rest = self._printed(_result(metadata={}))
        self.assertIn("nothing recorded", rest)


if __name__ == "__main__":
    unittest.main()
