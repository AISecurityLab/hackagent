# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the sidebar/header consolidation in DashboardLayoutMixin.

The top bar was removed; the drawer-collapse toggle, dark-mode toggle, and
refresh button now all live in the sidebar, plus a floating button to
re-open the sidebar once it's collapsed.
"""

import unittest
from unittest.mock import MagicMock, patch

from hackagent.server.dashboard import _layout_mixin
from hackagent.server.dashboard._layout_mixin import DashboardLayoutMixin


class _FakeDark:
    def __init__(self, value: bool = False) -> None:
        self.value = value


class _Page(DashboardLayoutMixin):
    def __init__(self) -> None:
        self.dark = _FakeDark()
        self.nav_buttons: dict = {}
        self.navigate = MagicMock()
        self._toggle_dark = MagicMock()
        self.refresh_view = MagicMock()
        self._on_runs_search_change = MagicMock()
        self._on_runs_filter_change = MagicMock()
        self._compare_selected_runs = MagicMock()
        self._export_selected_runs = MagicMock()
        self._delete_selected_runs = MagicMock()
        self._on_runs_table_select = MagicMock()
        self._load_more_runs = MagicMock()
        self._open_run_history_results = MagicMock()


def _button_calls_by_icon(mock_ui: MagicMock, icon: str) -> list:
    return [
        call
        for call in mock_ui.button.call_args_list
        if call.kwargs.get("icon") == icon
    ]


class TestBuildSidebar(unittest.TestCase):
    def setUp(self) -> None:
        patcher = patch.object(_layout_mixin, "ui", MagicMock())
        self.mock_ui = patcher.start()
        self.addCleanup(patcher.stop)

    def _build(self):
        page = _Page()
        sidebar = page._build_sidebar()
        return page, self.mock_ui, sidebar

    def test_returns_the_left_drawer(self):
        _, mock_ui, sidebar = self._build()

        expected_sidebar = (
            mock_ui.left_drawer.return_value.props.return_value.__enter__.return_value
        )
        self.assertIs(sidebar, expected_sidebar)

    def test_collapse_button_hides_the_sidebar(self):
        _, mock_ui, sidebar = self._build()

        collapse_calls = _button_calls_by_icon(mock_ui, "menu_open")
        self.assertEqual(len(collapse_calls), 1)
        collapse_calls[0].kwargs["on_click"]()

        sidebar.hide.assert_called_once_with()

    def test_floating_button_reopens_the_sidebar(self):
        _, mock_ui, sidebar = self._build()

        reopen_calls = _button_calls_by_icon(mock_ui, "menu")
        self.assertEqual(len(reopen_calls), 1)
        reopen_calls[0].kwargs["on_click"]()

        sidebar.show.assert_called_once_with()
        reopen_button = mock_ui.button.return_value
        reopen_button.props.return_value.classes.assert_any_call(
            "fixed top-2 left-2 z-50"
        )

    def test_nav_buttons_are_registered_for_every_view(self):
        page, mock_ui, _ = self._build()

        self.assertEqual(
            set(page.nav_buttons), {"dashboard", "agents", "runs", "builder"}
        )
        nav_calls = {
            call.args[0]: call.kwargs["on_click"]
            for call in mock_ui.button.call_args_list
            if call.args
            and call.args[0] in ("Home", "Targets", "History", "Attack Builder")
        }
        self.assertEqual(len(nav_calls), 4)
        nav_calls["Home"]()
        page.navigate.assert_called_once_with("dashboard")

    def test_dark_and_refresh_actions_moved_into_the_sidebar(self):
        page, mock_ui, _ = self._build()

        self.assertIsNotNone(page.dark_btn)
        dark_calls = _button_calls_by_icon(mock_ui, "dark_mode")
        self.assertEqual(len(dark_calls), 1)
        self.assertIs(dark_calls[0].kwargs["on_click"], page._toggle_dark)

        refresh_calls = _button_calls_by_icon(mock_ui, "refresh")
        self.assertEqual(len(refresh_calls), 1)
        refresh_calls[0].kwargs["on_click"]()
        mock_ui.timer.assert_called_once_with(0, page.refresh_view, once=True)

        self.assertIs(page.loading_spinner, mock_ui.spinner.return_value)
        page.loading_spinner.set_visibility.assert_called_once_with(False)


class TestBuildRunsPanel(unittest.TestCase):
    """The History view is now a vertical split (run list | detail/compare)."""

    def setUp(self) -> None:
        patcher = patch.object(_layout_mixin, "ui", MagicMock())
        self.mock_ui = patcher.start()
        self.addCleanup(patcher.stop)

    def test_uses_the_full_viewport_height_now_the_header_is_gone(self):
        page = _Page()
        page._build_runs_list = MagicMock()
        panel = MagicMock()

        page._build_runs_panel(panel)

        panel.classes.assert_called_once_with("w-full h-[calc(100vh-60px)] min-h-0")

    def test_builds_left_column_and_side_panel_and_delegates_the_list(self):
        page = _Page()
        page._build_runs_list = MagicMock()

        page._build_runs_panel(MagicMock())

        self.assertIsNotNone(page._runs_left_col)
        self.assertIsNotNone(page._runs_side_panel)
        page._build_runs_list.assert_called_once_with()

    def test_side_panel_hosts_run_detail_and_compare_cards_hidden_by_default(self):
        page = _Page()
        page._build_runs_list = MagicMock()

        page._build_runs_panel(MagicMock())

        self.assertEqual(self.mock_ui.card.call_count, 2)
        for call in self.mock_ui.card.return_value.classes.call_args_list:
            self.assertEqual(call.args[0], "w-full h-full gap-0 hidden")
        self.assertIsNotNone(page._runs_bottom_panel)
        self.assertIsNotNone(page._compare_bottom_panel)


class TestBuildRunsList(unittest.TestCase):
    def setUp(self) -> None:
        ui_patcher = patch.object(_layout_mixin, "ui", MagicMock())
        self.mock_ui = ui_patcher.start()
        self.addCleanup(ui_patcher.stop)

        table_patcher = patch.object(_layout_mixin, "make_run_table", MagicMock())
        self.mock_make_run_table = table_patcher.start()
        self.addCleanup(table_patcher.stop)

    def _search_handler(self):
        chain = self.mock_ui.input.return_value.props.return_value.classes.return_value
        event_name, handler = chain.on.call_args.args
        self.assertEqual(event_name, "update:model-value")
        return handler

    def test_search_input_forwards_string_args_to_the_search_handler(self):
        page = _Page()
        page._build_runs_list()

        handler = self._search_handler()
        handler(MagicMock(args="needle"))

        page._on_runs_search_change.assert_called_once_with("needle")

    def test_search_input_falls_back_to_empty_string_for_non_string_args(self):
        page = _Page()
        page._build_runs_list()

        handler = self._search_handler()
        handler(MagicMock(args=None))

        page._on_runs_search_change.assert_called_once_with("")

    def test_agent_and_attack_selects_forward_to_filter_change(self):
        page = _Page()
        page._build_runs_list()

        agent_kwargs = self.mock_ui.select.call_args_list[0].kwargs
        attack_kwargs = self.mock_ui.select.call_args_list[1].kwargs
        agent_kwargs["on_change"](MagicMock(value="agent-1"))
        attack_kwargs["on_change"](MagicMock(value="attack-1"))

        page._on_runs_filter_change.assert_any_call("agent", "agent-1")
        page._on_runs_filter_change.assert_any_call("attack", "attack-1")

    def test_compare_export_delete_buttons_schedule_their_handlers(self):
        page = _Page()
        page._build_runs_list()

        buttons = {
            call.args[0]: call.kwargs["on_click"]
            for call in self.mock_ui.button.call_args_list
            if call.args and call.args[0] in ("Compare", "Export", "Delete")
        }
        self.assertEqual(set(buttons), {"Compare", "Export", "Delete"})

        buttons["Compare"]()
        self.mock_ui.timer.assert_called_with(0, page._compare_selected_runs, once=True)
        buttons["Export"]()
        self.mock_ui.timer.assert_called_with(0, page._export_selected_runs, once=True)
        buttons["Delete"]()
        self.mock_ui.timer.assert_called_with(0, page._delete_selected_runs, once=True)

    def test_runs_table_is_built_with_the_expected_columns_and_selection(self):
        page = _Page()
        page._build_runs_list()

        _, kwargs = self.mock_make_run_table.call_args
        self.assertEqual(
            {
                "include_agent": kwargs["include_agent"],
                "include_progressive_run": kwargs["include_progressive_run"],
                "include_results": kwargs["include_results"],
                "include_goal_latency_avg": kwargs["include_goal_latency_avg"],
                "include_asr": kwargs["include_asr"],
                "pagination": kwargs["pagination"],
                "selection": kwargs["selection"],
            },
            {
                "include_agent": True,
                "include_progressive_run": True,
                "include_results": False,
                "include_goal_latency_avg": True,
                "include_asr": True,
                "pagination": {"rowsPerPage": 15},
                "selection": "multiple",
            },
        )
        self.assertIs(page.runs_table, self.mock_make_run_table.return_value)

        kwargs["on_select"](MagicMock(name="select-event"))
        page._on_runs_table_select.assert_called_once()

    def test_load_more_button_schedules_load_more_runs(self):
        page = _Page()
        page._build_runs_list()

        load_more_calls = [
            call
            for call in self.mock_ui.button.call_args_list
            if call.args and call.args[0] == "Load more"
        ]
        self.assertEqual(len(load_more_calls), 1)

        load_more_calls[0].kwargs["on_click"]()
        self.mock_ui.timer.assert_called_with(0, page._load_more_runs, once=True)
