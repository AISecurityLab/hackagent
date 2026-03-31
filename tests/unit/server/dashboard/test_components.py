# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for dashboard UI component factories."""

from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from hackagent.server.dashboard._components import make_run_table


class _FakeTable:
    def __init__(self):
        self.handlers = {}

    def classes(self, _value):
        return self

    def add_slot(self, _name, _template):
        return None

    def on(self, event_name, handler):
        self.handlers.setdefault(event_name, []).append(handler)


class TestMakeRunTable(unittest.TestCase):
    """Test column configuration and click event handling."""

    def test_make_run_table_columns_follow_flags(self):
        fake_table = _FakeTable()
        on_row_click = MagicMock()

        with patch(
            "hackagent.server.dashboard._components.ui.table",
            return_value=fake_table,
        ) as mock_ui_table:
            table = make_run_table(
                on_row_click=on_row_click,
                include_agent=True,
                include_progressive_run=True,
                include_results=False,
                include_goal_latency_avg=True,
            )

        self.assertIs(table, fake_table)
        _, kwargs = mock_ui_table.call_args
        columns = kwargs["columns"]

        self.assertEqual(columns[0]["label"], "Run #")
        self.assertEqual(columns[0]["field"], "run_progress")
        self.assertTrue(any(c["name"] == "agent_name" for c in columns))
        self.assertTrue(any(c["name"] == "goal_latency_avg" for c in columns))
        self.assertFalse(any(c["name"] == "results" for c in columns))

    def test_make_run_table_deduplicates_near_simultaneous_row_clicks(self):
        fake_table = _FakeTable()
        on_row_click = MagicMock()

        with patch(
            "hackagent.server.dashboard._components.ui.table",
            return_value=fake_table,
        ):
            make_run_table(on_row_click=on_row_click)

        row_click_handler = fake_table.handlers["rowClick"][0]
        native_click_handler = fake_table.handlers["row-click"][0]

        with patch(
            "hackagent.server.dashboard._components.time.monotonic",
            side_effect=[10.0, 10.1, 11.0],
        ):
            row_click_handler(SimpleNamespace(args={"row": {"id": "run-1"}}))
            native_click_handler(SimpleNamespace(args={"row": {"id": "run-1"}}))
            native_click_handler(SimpleNamespace(args={"row": {"id": "run-2"}}))

        self.assertEqual(on_row_click.call_count, 2)
        self.assertEqual(on_row_click.call_args_list[0].args[0]["id"], "run-1")
        self.assertEqual(on_row_click.call_args_list[1].args[0]["id"], "run-2")


if __name__ == "__main__":
    unittest.main()
