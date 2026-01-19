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
Basic Integration Tests for ResultsTab Widget.

Tests the core functionality of the ResultsTab widget including:
- Widget instantiation and initialization
- Table setup and column configuration
- Data loading from API
- Error handling
"""

from datetime import datetime
from unittest.mock import Mock, patch
from uuid import uuid4

import httpx
import pytest
from textual.app import App
from textual.widgets import DataTable, Static, Select, Button

from hackagent.cli.config import CLIConfig
from hackagent.cli.tui.views.results import ResultsTab


@pytest.fixture
def cli_config():
    """Create a test CLI configuration."""
    config = Mock(spec=CLIConfig)
    config.api_key = "test-api-key-12345"
    config.base_url = "https://api.test.hackagent.dev"
    return config


@pytest.fixture
def mock_run():
    """Create a mock run object with typical structure."""
    run = Mock()
    run.id = uuid4()
    run.agent_name = "test-agent"
    run.status = Mock(value="COMPLETED")
    run.timestamp = datetime(2026, 1, 19, 10, 0, 0)
    run.results = []
    return run


@pytest.fixture
def mock_run_with_results():
    """Create a mock run with results."""
    run = Mock()
    run.id = uuid4()
    run.agent_name = "test-agent-with-results"
    run.status = Mock(value="COMPLETED")
    run.timestamp = datetime(2026, 1, 19, 10, 0, 0)

    # Add mock results
    result1 = Mock()
    result1.id = uuid4()
    result1.evaluation_status = Mock(value="SUCCESSFUL_JAILBREAK")
    result1.created_at = datetime(2026, 1, 19, 10, 5, 0)

    result2 = Mock()
    result2.id = uuid4()
    result2.evaluation_status = Mock(value="FAILED_JAILBREAK")
    result2.created_at = datetime(2026, 1, 19, 10, 6, 0)

    run.results = [result1, result2]
    return run


class TestResultsTabInstantiation:
    """Test ResultsTab widget instantiation and initialization."""

    def test_results_tab_creates_successfully(self, cli_config):
        """Test that ResultsTab can be instantiated."""
        tab = ResultsTab(cli_config)

        assert tab.cli_config == cli_config
        assert tab.results_data == []
        assert tab.selected_result is None
        assert tab._detail_page == 0
        assert tab._run_id_map == {}

    def test_results_tab_has_correct_bindings(self, cli_config):
        """Test that ResultsTab has the expected key bindings."""
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
        """Test that max display constants are set."""
        tab = ResultsTab(cli_config)

        assert hasattr(tab, "MAX_RESULTS_DISPLAY")
        assert tab.MAX_RESULTS_DISPLAY == 10
        assert hasattr(tab, "MAX_TRACES_PER_RESULT")
        assert tab.MAX_TRACES_PER_RESULT == 5
        assert hasattr(tab, "MAX_CONTENT_LENGTH")
        assert tab.MAX_CONTENT_LENGTH == 500


class TestResultsTabMounting:
    """Test ResultsTab widget mounting and composition."""

    @pytest.mark.asyncio
    async def test_results_tab_mounts_successfully(self, cli_config):
        """Test that ResultsTab can be mounted in an app."""

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
        """Test that table columns are set up when mounted."""

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
        """Test that all required widgets are present."""

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
        """Test that status filter has all expected options."""

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
        """Test that limit selector has expected options."""

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


class TestResultsDataLoading:
    """Test results data loading and API integration."""

    @pytest.mark.asyncio
    @patch("hackagent.api.run.run_list.sync_detailed")
    async def test_refresh_data_success(self, mock_api, cli_config, mock_run):
        """Test successful data refresh from API."""
        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.parsed = Mock()
        mock_response.parsed.results = [mock_run]
        mock_api.return_value = mock_response

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)
            tab.refresh_data()

            # Verify data was loaded
            assert len(tab.results_data) == 1
            assert tab.results_data[0].id == mock_run.id
            assert tab.results_data[0].agent_name == "test-agent"

            # Verify API was called with correct params
            assert mock_api.called
            call_kwargs = mock_api.call_args[1]
            assert call_kwargs["page_size"] == 25

    @pytest.mark.asyncio
    @patch("hackagent.api.run.run_list.sync_detailed")
    async def test_refresh_data_with_multiple_runs(
        self, mock_api, cli_config, mock_run, mock_run_with_results
    ):
        """Test loading multiple runs."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.parsed = Mock()
        mock_response.parsed.results = [mock_run, mock_run_with_results]
        mock_api.return_value = mock_response

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)
            tab.refresh_data()

            assert len(tab.results_data) == 2

    @pytest.mark.asyncio
    @patch("hackagent.api.run.run_list.sync_detailed")
    async def test_refresh_data_handles_empty_response(self, mock_api, cli_config):
        """Test handling empty results from API."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.parsed = Mock()
        mock_response.parsed.results = []
        mock_api.return_value = mock_response

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)
            tab.refresh_data()

            assert len(tab.results_data) == 0

    @pytest.mark.asyncio
    @patch("hackagent.api.run.run_list.sync_detailed")
    async def test_refresh_data_handles_401_unauthorized(self, mock_api, cli_config):
        """Test handling 401 authentication error."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.parsed = None
        mock_api.return_value = mock_response

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)
            tab.refresh_data()

            # Should show empty state, not crash
            assert len(tab.results_data) == 0

    @pytest.mark.asyncio
    @patch("hackagent.api.run.run_list.sync_detailed")
    async def test_refresh_data_handles_403_forbidden(self, mock_api, cli_config):
        """Test handling 403 access forbidden error."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.parsed = None
        mock_api.return_value = mock_response

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)
            tab.refresh_data()

            assert len(tab.results_data) == 0

    @pytest.mark.asyncio
    @patch("hackagent.api.run.run_list.sync_detailed")
    async def test_refresh_data_handles_timeout(self, mock_api, cli_config):
        """Test timeout handling during refresh."""
        mock_api.side_effect = httpx.TimeoutException("Connection timeout")

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)
            tab.refresh_data()

            # Should not crash
            assert len(tab.results_data) == 0

    @pytest.mark.asyncio
    @patch("hackagent.api.run.run_list.sync_detailed")
    async def test_refresh_data_handles_generic_exception(self, mock_api, cli_config):
        """Test generic exception handling."""
        mock_api.side_effect = Exception("Network error")

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)
            tab.refresh_data()

            # Should handle gracefully
            assert len(tab.results_data) == 0

    @pytest.mark.asyncio
    async def test_refresh_data_without_api_key(self, cli_config):
        """Test refresh when API key is not configured."""
        cli_config.api_key = None

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)
            tab.refresh_data()

            # Should handle gracefully
            assert len(tab.results_data) == 0

    @pytest.mark.asyncio
    @patch("hackagent.api.run.run_list.sync_detailed")
    async def test_refresh_data_with_status_filter(
        self, mock_api, cli_config, mock_run
    ):
        """Test refresh with status filter applied."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.parsed = Mock()
        mock_response.parsed.results = [mock_run]
        mock_api.return_value = mock_response

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)
            # Manually set filter value (in real scenario this comes from UI)
            # We'll just test the API call logic
            tab.refresh_data()

            # Should call API
            assert mock_api.called


class TestResultsTableUpdate:
    """Test table update and display logic."""

    @pytest.mark.asyncio
    async def test_update_table_with_data(self, cli_config, mock_run):
        """Test that table updates correctly with data."""

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)
            tab.results_data = [mock_run]
            tab._update_table()

            table = tab.query_one("#results-table", DataTable)
            assert table.row_count == 1

    @pytest.mark.asyncio
    async def test_update_table_with_multiple_runs(
        self, cli_config, mock_run, mock_run_with_results
    ):
        """Test table with multiple runs."""

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)
            tab.results_data = [mock_run, mock_run_with_results]
            tab._update_table()

            table = tab.query_one("#results-table", DataTable)
            assert table.row_count == 2

    @pytest.mark.asyncio
    async def test_update_table_builds_run_id_map(self, cli_config, mock_run):
        """Test that run ID mapping is built correctly."""

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)
            tab.results_data = [mock_run]
            tab._update_table()

            # Verify mapping was created
            assert len(tab._run_id_map) == 1
            assert str(mock_run.id) in tab._run_id_map

    @pytest.mark.asyncio
    async def test_update_table_clears_previous_data(self, cli_config, mock_run):
        """Test that table clears previous data before updating."""

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        async with app.run_test() as _:
            tab = app.query_one(ResultsTab)

            # Add initial data
            tab.results_data = [mock_run]
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
    """Test empty state handling."""

    @pytest.mark.asyncio
    async def test_show_empty_state(self, cli_config):
        """Test displaying empty state message."""

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
        """Test that empty state clears the table."""

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
        """Test that empty state clears results container."""

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
    """Test pagination functionality."""

    @pytest.mark.asyncio
    async def test_action_next_page_increments(self, cli_config, mock_run_with_results):
        """Test next page action increments page number."""

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
        """Test previous page action decrements page number."""
        tab = ResultsTab(cli_config)
        tab._detail_page = 1

        tab.action_prev_page()

        assert tab._detail_page == 0

    def test_prev_page_does_not_go_negative(self, cli_config):
        """Test that previous page doesn't go below 0."""
        tab = ResultsTab(cli_config)
        tab._detail_page = 0

        tab.action_prev_page()

        assert tab._detail_page == 0

    def test_next_page_respects_max_pages(self, cli_config):
        """Test that next page respects maximum pages."""
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
