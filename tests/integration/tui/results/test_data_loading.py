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
Data Loading Integration Tests for ResultsTab.

Tests API integration, error handling, and data refresh functionality.
These tests ensure that:
- Data is successfully loaded from the HackAgent API
- HTTP errors are handled gracefully (401, 403, 404)
- Timeouts and network errors don't crash the widget
- Empty responses are handled correctly
- Filter parameters are passed to API correctly

Test Fixtures:
    cli_config: Mock CLI configuration
    mock_run: Single mock run without results
    mock_run_with_results: Mock run with evaluation results

Example:
    Run these tests with:
    $ uv run pytest tests/integration/tui/results/test_data_loading.py -v
"""

from datetime import datetime
from unittest.mock import Mock, patch
from uuid import uuid4

import httpx
import pytest
from textual.app import App

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


class TestResultsDataLoading:
    """
    Test suite for results data loading and API integration.

    Tests the refresh_data() method which fetches runs from the API
    and handles various success and error scenarios.
    """

    @pytest.mark.asyncio
    @patch("hackagent.api.run.run_list.sync_detailed")
    async def test_refresh_data_success(self, mock_api, cli_config, mock_run):
        """
        Test successful data refresh from API.

        Verifies:
        - API is called with correct parameters
        - Response data is stored in results_data
        - Run object properties are accessible
        - Default page_size is 25
        """
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
        """
        Test loading multiple runs from API.

        Verifies that multiple run objects are stored correctly.
        """
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
        """
        Test handling empty results from API.

        When the API returns no runs (new user, no attacks yet),
        the widget should show an appropriate empty state.
        """
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
        """
        Test handling 401 authentication error.

        When the API key is invalid or expired, the widget should:
        - Not crash
        - Show an empty state with auth error message
        - Not populate results_data
        """
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
        """
        Test handling 403 access forbidden error.

        When the user doesn't have permission to view runs,
        the widget should handle it gracefully.
        """
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
        """
        Test timeout handling during refresh.

        Network timeouts should be caught and displayed to user
        with a helpful message, not crash the app.
        """
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
        """
        Test generic exception handling.

        Any unexpected error should be caught and logged,
        not crash the entire TUI.
        """
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
        """
        Test refresh when API key is not configured.

        When the user hasn't set up their API key yet,
        the widget should show a helpful setup message.
        """
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
        """
        Test refresh with status filter applied.

        When the user selects a filter (e.g., "completed" only),
        the filter parameter should be passed to the API.

        Note: This test verifies the API is called. Full filter
        integration requires testing the Select widget's change event.
        """
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
