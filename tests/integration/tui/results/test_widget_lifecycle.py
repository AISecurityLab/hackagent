# Copyright 2025 - AI4I. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Widget Lifecycle Integration Tests for ResultsTab.

Tests the instantiation, mounting, and composition of the ResultsTab widget.
These tests ensure that:
- The widget can be created with proper initialization
- All required sub-widgets (buttons, tables, selects) are present
- Key bindings are registered correctly
- Widget mounts successfully in a Textual app
- Table columns are set up properly

Test Fixtures:
    cli_config: Mock CLI configuration with API key and base URL

Example:
    Run these tests with:
    $ uv run pytest tests/integration/tui/results/test_widget_lifecycle.py -v
"""

from datetime import datetime
from unittest.mock import Mock
from uuid import uuid4

import pytest
from textual.app import App
from textual.widgets import DataTable, Static, Select, Button

from hackagent.cli.config import CLIConfig
from hackagent.cli.tui.views.results import ResultsTab


@pytest.fixture
def cli_config():
    """Create a test CLI configuration.

    Returns:
        Mock CLIConfig with test API credentials
    """
    config = Mock(spec=CLIConfig)
    config.api_key = "test-api-key-12345"
    config.base_url = "https://api.test.hackagent.dev"
    return config


class TestResultsTabInstantiation:
    """
    Test suite for ResultsTab widget instantiation and initialization.

    Verifies that the widget can be created and has the correct
    default values for properties.
    """

    def test_results_tab_creates_successfully(self, cli_config):
        """
        Test that ResultsTab can be instantiated with CLI config.

        Verifies:
        - Widget accepts CLIConfig parameter
        - Results data starts as empty list
        - No result is initially selected
        - Detail page starts at 0
        - Run ID map is empty
        """
        tab = ResultsTab(cli_config)

        assert tab.cli_config == cli_config
        assert tab.results_data == []
        assert tab.selected_result is None
        assert tab._detail_page == 0
        assert tab._run_id_map == {}

    def test_results_tab_has_correct_bindings(self, cli_config):
        """
        Test that ResultsTab has the expected key bindings.

        Verifies that keyboard shortcuts are registered for:
        - enter: View result details
        - s: Show summary
        - [: Previous page
        - ]: Next page
        - pageup/pagedown: Page navigation
        """
        tab = ResultsTab(cli_config)

        # Check bindings are defined
        assert len(tab.BINDINGS) > 0

        # Check for specific bindings
        binding_keys = [b.key for b in tab.BINDINGS]
        assert "enter" in binding_keys
        assert "s" in binding_keys
        assert "[" in binding_keys
        assert "]" in binding_keys

    def test_results_tab_has_max_constants(self, cli_config):
        """
        Test that max display constants are set correctly.

        These constants control pagination and prevent UI freezing
        with large datasets:
        - MAX_RESULTS_DISPLAY: Results per page (10)
        - MAX_TRACES_PER_RESULT: Traces shown per result (5)
        - MAX_CONTENT_LENGTH: Max chars before truncation (500)
        """
        tab = ResultsTab(cli_config)

        assert hasattr(tab, "MAX_RESULTS_DISPLAY")
        assert tab.MAX_RESULTS_DISPLAY == 10
        assert hasattr(tab, "MAX_TRACES_PER_RESULT")
        assert tab.MAX_TRACES_PER_RESULT == 5
        assert hasattr(tab, "MAX_CONTENT_LENGTH")
        assert tab.MAX_CONTENT_LENGTH == 500


class TestResultsTabMounting:
    """
    Test suite for ResultsTab widget mounting and composition.

    Tests that verify the widget can be mounted in a Textual app
    and all required sub-widgets are present and configured correctly.
    """

    @pytest.mark.asyncio
    async def test_results_tab_mounts_successfully(self, cli_config):
        """
        Test that ResultsTab can be mounted in a Textual app.

        This is the most basic integration test - it verifies the widget
        can be composed and mounted without errors.
        """

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            # Tab should be present
            tab = app.query_one(ResultsTab)
            assert tab is not None
            assert tab.cli_config == cli_config

    @pytest.mark.asyncio
    async def test_table_columns_initialized_on_mount(self, cli_config):
        """
        Test that DataTable columns are set up when widget mounts.

        The results table should have 5 columns:
        1. # (Run number)
        2. ⚡ (Status indicator)
        3. Agent (Agent name)
        4. ✅/❌ (Success/fail ratio)
        5. Created (Timestamp)
        """

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)
            table = tab.query_one("#results-table", DataTable)

            # Check table exists and has columns
            assert table is not None
            assert len(table.columns) == 5

            # Verify column labels exist
            columns = list(table.columns.keys())
            assert len(columns) == 5

    @pytest.mark.asyncio
    async def test_results_tab_has_all_required_widgets(self, cli_config):
        """
        Test that all required sub-widgets are present after mounting.

        The ResultsTab should contain:
        - Results table (DataTable)
        - Left panel (results list)
        - Right panel (detail view)
        - Header static (summary info)
        - Results container (for details)
        - Action buttons (refresh, export)
        - Filter controls (status, limit)
        """

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)

            # Check for key widgets
            assert tab.query_one("#results-table", DataTable) is not None
            assert tab.query_one("#results-left-panel") is not None
            assert tab.query_one("#results-right-panel") is not None
            assert tab.query_one("#run-header-static", Static) is not None
            assert tab.query_one("#results-container") is not None

            # Check for controls
            assert tab.query_one("#refresh-results", Button) is not None
            assert tab.query_one("#export-csv", Button) is not None
            assert tab.query_one("#export-json", Button) is not None
            assert tab.query_one("#status-filter", Select) is not None
            assert tab.query_one("#limit-select", Select) is not None

    @pytest.mark.asyncio
    async def test_status_filter_has_correct_options(self, cli_config):
        """
        Test that status filter dropdown has all expected options.

        The status filter should provide:
        - All (default)
        - Pending
        - Running
        - Completed
        - Failed
        """

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)
            status_filter = tab.query_one("#status-filter", Select)

            # Check default value
            assert status_filter.value == "all"

            # Check options exist
            options = [(str(o[0]), str(o[1])) for o in status_filter._options]
            assert ("All", "all") in options
            assert ("Pending", "pending") in options
            assert ("Running", "running") in options
            assert ("Completed", "completed") in options
            assert ("Failed", "failed") in options

    @pytest.mark.asyncio
    async def test_limit_select_has_correct_options(self, cli_config):
        """
        Test that limit selector has expected options.

        The limit selector controls how many results to fetch:
        - 10
        - 25 (default)
        - 50
        - 100
        """

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)
            limit_select = tab.query_one("#limit-select", Select)

            # Check default value
            assert limit_select.value == "25"

            # Check options
            options = [(str(o[0]), str(o[1])) for o in limit_select._options]
            assert ("10", "10") in options
            assert ("25", "25") in options
            assert ("50", "50") in options
            assert ("100", "100") in options


class TestResultsTableUpdate:
    """
    Test suite for table update and display logic.

    Tests that verify the results table updates correctly when
    data is loaded, including proper row formatting and ID mapping.
    """

    @pytest.mark.asyncio
    async def test_update_table_with_data(self, cli_config):
        """
        Test that table updates correctly with single run.

        Verifies that _update_table() populates the DataTable
        with one row when given one run.
        """

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)

            # Create mock run
            mock_run = Mock()
            mock_run.id = uuid4()
            mock_run.agent_name = "test-agent"
            mock_run.status = Mock(value="COMPLETED")
            mock_run.timestamp = datetime(2026, 1, 19, 10, 0, 0)
            mock_run.results = []

            tab.results_data = [mock_run]
            tab._update_table()

            table = tab.query_one("#results-table", DataTable)
            assert table.row_count == 1

    @pytest.mark.asyncio
    async def test_update_table_with_multiple_runs(self, cli_config):
        """
        Test table with multiple runs.

        Verifies that multiple rows are added correctly.
        """

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)

            # Create multiple mock runs
            mock_run1 = Mock()
            mock_run1.id = uuid4()
            mock_run1.agent_name = "agent-1"
            mock_run1.status = Mock(value="COMPLETED")
            mock_run1.timestamp = datetime(2026, 1, 19, 10, 0, 0)
            mock_run1.results = []

            mock_run2 = Mock()
            mock_run2.id = uuid4()
            mock_run2.agent_name = "agent-2"
            mock_run2.status = Mock(value="RUNNING")
            mock_run2.timestamp = datetime(2026, 1, 19, 11, 0, 0)
            mock_run2.results = []

            tab.results_data = [mock_run1, mock_run2]
            tab._update_table()

            table = tab.query_one("#results-table", DataTable)
            assert table.row_count == 2

    @pytest.mark.asyncio
    async def test_update_table_builds_run_id_map(self, cli_config):
        """
        Test that run ID mapping is built correctly.

        The _run_id_map allows looking up run objects by their ID
        when a row is selected.
        """

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)

            mock_run = Mock()
            mock_run.id = uuid4()
            mock_run.agent_name = "test-agent"
            mock_run.status = Mock(value="COMPLETED")
            mock_run.timestamp = datetime(2026, 1, 19, 10, 0, 0)
            mock_run.results = []

            tab.results_data = [mock_run]
            tab._update_table()

            # Verify mapping was created
            assert len(tab._run_id_map) == 1
            assert str(mock_run.id) in tab._run_id_map

    @pytest.mark.asyncio
    async def test_update_table_clears_previous_data(self, cli_config):
        """
        Test that table clears previous data before updating.

        When _update_table() is called multiple times, it should
        clear old data and show only new data.
        """

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)

            # Add initial data
            mock_run1 = Mock()
            mock_run1.id = uuid4()
            mock_run1.agent_name = "agent-1"
            mock_run1.status = Mock(value="COMPLETED")
            mock_run1.timestamp = datetime(2026, 1, 19, 10, 0, 0)
            mock_run1.results = []

            tab.results_data = [mock_run1]
            tab._update_table()

            table = tab.query_one("#results-table", DataTable)

            # Update with new data
            mock_run2 = Mock()
            mock_run2.id = uuid4()
            mock_run2.agent_name = "agent-2"
            mock_run2.status = Mock(value="RUNNING")
            mock_run2.timestamp = datetime(2026, 1, 19, 11, 0, 0)
            mock_run2.results = []

            tab.results_data = [mock_run2]
            tab._update_table()

            # Should have only the new data
            assert table.row_count == 1


class TestResultsEmptyStates:
    """
    Test suite for empty state handling.

    Tests that verify the widget displays appropriate messages
    when no data is available or errors occur.
    """

    @pytest.mark.asyncio
    async def test_show_empty_state(self, cli_config):
        """
        Test displaying empty state message.

        The _show_empty_state() method should update the header
        widget with a user-friendly message.
        """

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)
            tab._show_empty_state("No results found")

            # Verify message is displayed
            header = tab.query_one("#run-header-static", Static)
            # Check the rendered output
            rendered = str(header.render())
            assert "No results found" in rendered

    @pytest.mark.asyncio
    async def test_empty_state_clears_table(self, cli_config):
        """
        Test that empty state clears the table.

        When showing an empty state, the results table should
        be cleared to avoid confusion.
        """

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)
            tab._show_empty_state("Test message")

            table = tab.query_one("#results-table", DataTable)
            assert table.row_count == 0

    @pytest.mark.asyncio
    async def test_empty_state_clears_results_container(self, cli_config):
        """
        Test that empty state clears results container.

        The details panel should also be cleared when showing
        an empty state.
        """

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)
            tab._show_empty_state("Test message")

            container = tab.query_one("#results-container")
            assert len(container.children) == 0


class TestResultsPagination:
    """
    Test suite for pagination functionality.

    Tests for navigating between pages of result details when
    a run has more results than MAX_RESULTS_DISPLAY.
    """

    @pytest.mark.asyncio
    async def test_action_next_page_increments(self, cli_config):
        """
        Test next page action increments page number.

        When viewing a run with 15 results (MAX_RESULTS_DISPLAY=10),
        next page should move from page 0 to page 1.
        """

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)

            # Create run with 15 results (more than MAX_RESULTS_DISPLAY)
            run = Mock()
            run.results = [Mock(id=f"r-{i}") for i in range(15)]
            tab.selected_result = run
            tab._detail_page = 0

            tab.action_next_page()

            assert tab._detail_page == 1

    def test_action_prev_page_decrements(self, cli_config):
        """
        Test previous page action decrements page number.

        Moving from page 1 to page 0.
        """
        tab = ResultsTab(cli_config)
        tab._detail_page = 1

        tab.action_prev_page()

        assert tab._detail_page == 0

    def test_prev_page_does_not_go_negative(self, cli_config):
        """
        Test that previous page doesn't go below 0.

        Page number should never be negative.
        """
        tab = ResultsTab(cli_config)
        tab._detail_page = 0

        tab.action_prev_page()

        assert tab._detail_page == 0

    def test_next_page_respects_max_pages(self, cli_config):
        """
        Test that next page respects maximum pages.

        If on the last page, next page shouldn't increment.
        """
        tab = ResultsTab(cli_config)

        # Create run with exactly MAX_RESULTS_DISPLAY results
        run = Mock()
        run.results = [Mock(id=f"r-{i}") for i in range(tab.MAX_RESULTS_DISPLAY)]
        tab.selected_result = run
        tab._detail_page = 0

        # Should not increment since we're on the last page
        initial_page = tab._detail_page
        tab.action_next_page()

        # Should stay on same page (only 1 page total)
        assert tab._detail_page == initial_page
