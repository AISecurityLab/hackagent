# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the History side panel behaviour and Home → History redirect."""

import unittest

from hackagent.server.dashboard._reports_mixin import DashboardReportsMixin
from hackagent.server.dashboard._runs_mixin import DashboardRunsMixin


class _FakeClasses(list):
    def __call__(self, add=None, remove=None):
        if remove:
            for name in remove.split():
                while name in self:
                    self.remove(name)
        if add:
            self.extend(name for name in add.split() if name not in self)
        return self


class _FakeElement:
    def __init__(self, *classes: str) -> None:
        self.classes = _FakeClasses(classes)
        self.style_value = ""

    def style(self, value: str) -> "_FakeElement":
        self.style_value = value
        return self


class _FakePage(DashboardRunsMixin, DashboardReportsMixin):
    def __init__(self) -> None:
        self.current_view = {"value": "dashboard"}
        self.navigated: list[str] = []
        self._runs_left_col = _FakeElement("w-full")
        self._runs_side_panel = _FakeElement()
        self._runs_bottom_panel = _FakeElement("hidden")
        self._compare_bottom_panel = _FakeElement("hidden")

    def navigate(self, view: str) -> None:
        self.navigated.append(view)
        self.current_view["value"] = view


class TestRunsSidePanel(unittest.TestCase):
    def test_opening_a_run_from_home_redirects_to_history(self):
        page = _FakePage()

        page._open_runs_bottom_panel()

        self.assertEqual(page.navigated, ["runs"])
        self.assertEqual(page.current_view["value"], "runs")

    def test_opening_a_run_from_history_does_not_renavigate(self):
        page = _FakePage()
        page.current_view["value"] = "runs"

        page._open_runs_bottom_panel()

        self.assertEqual(page.navigated, [])

    def test_open_expands_side_panel_and_shrinks_run_list(self):
        page = _FakePage()

        page._open_runs_bottom_panel()

        self.assertNotIn("hidden", page._runs_bottom_panel.classes)
        self.assertIn("hidden", page._compare_bottom_panel.classes)
        self.assertIn("width: 68%", page._runs_side_panel.style_value)
        self.assertIn("w-[32%]", page._runs_left_col.classes)
        self.assertNotIn("w-full", page._runs_left_col.classes)

    def test_close_collapses_side_panel_and_restores_run_list(self):
        page = _FakePage()
        page._open_runs_bottom_panel()

        page._close_runs_bottom_panel()

        self.assertIn("hidden", page._runs_bottom_panel.classes)
        self.assertIn("width: 0", page._runs_side_panel.style_value)
        self.assertIn("w-full", page._runs_left_col.classes)

    def test_close_keeps_side_panel_open_while_compare_is_visible(self):
        page = _FakePage()
        page._open_runs_bottom_panel()
        page._compare_bottom_panel.classes(remove="hidden")

        page._close_runs_bottom_panel()

        self.assertIn("width: 68%", page._runs_side_panel.style_value)
        self.assertIn("w-[32%]", page._runs_left_col.classes)

    def test_close_compare_panel_collapses_side_panel_when_runs_panel_hidden(self):
        page = _FakePage()
        page._compare_bottom_panel.classes(remove="hidden")

        page._close_compare_panel()

        self.assertIn("hidden", page._compare_bottom_panel.classes)
        self.assertIn("width: 0", page._runs_side_panel.style_value)
        self.assertIn("w-full", page._runs_left_col.classes)

    def test_close_compare_panel_keeps_side_panel_open_while_runs_panel_visible(self):
        page = _FakePage()
        page._compare_bottom_panel.classes(remove="hidden")
        page._runs_bottom_panel.classes(remove="hidden")

        page._close_compare_panel()

        self.assertIn("hidden", page._compare_bottom_panel.classes)
        self.assertNotIn("width: 0", page._runs_side_panel.style_value)
