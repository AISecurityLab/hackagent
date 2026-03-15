# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Data Loading Integration Tests for ResultsTab.

Tests API integration, error handling, and data refresh functionality.
These tests ensure that:
- Data is successfully loaded from the backend
- Errors are handled gracefully (timeouts, exceptions)
- Empty responses are handled correctly

Test Fixtures:
    cli_config: Mock CLI configuration
    mock_run_record: Single mock RunRecord without results
    mock_run_record_2: A second mock RunRecord for multi-run tests

Example:
    Run these tests with:
    $ uv run pytest tests/integration/tui/results/test_data_loading.py -v
"""

from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4

import httpx
import pytest
from textual.app import App

from hackagent.cli.config import CLIConfig
from hackagent.cli.tui.views.results import ResultsTab
from hackagent.server.storage.base import RunRecord, PaginatedResult


@pytest.fixture
def cli_config():
    """Create a test CLI configuration."""
    config = Mock(spec=CLIConfig)
    config.api_key = "test-api-key-12345"
    config.base_url = "https://api.test.hackagent.dev"
    return config


def _make_run_record(**overrides):
    """Create a RunRecord with sensible defaults."""
    now = datetime.now(tz=timezone.utc)
    defaults = dict(
        id=uuid4(),
        attack_id=uuid4(),
        agent_id=uuid4(),
        run_config={},
        status="COMPLETED",
        run_notes=None,
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return RunRecord(**defaults)


def _make_mock_backend(runs=None, raise_on_list_runs=None):
    """Create a mock StorageBackend."""
    backend = MagicMock()
    if raise_on_list_runs is not None:
        backend.list_runs.side_effect = raise_on_list_runs
    else:
        items = runs if runs is not None else []
        backend.list_runs.return_value = PaginatedResult(items=items, total=len(items))
    backend.list_agents.return_value = PaginatedResult(items=[], total=0)
    backend.list_results.return_value = PaginatedResult(items=[], total=0)
    return backend


@pytest.fixture
def mock_run_record():
    """Create a single RunRecord for testing."""
    return _make_run_record()


@pytest.fixture
def mock_run_record_2():
    """Create a second RunRecord for multi-run testing."""
    return _make_run_record()


class TestResultsDataLoading:
    """
    Test suite for results data loading and API integration.

    Tests the refresh_data() method which fetches runs from the backend
    and handles various success and error scenarios.
    """

    @pytest.mark.asyncio
    async def test_refresh_data_success(self, cli_config, mock_run_record):
        """
        Test successful data refresh.

        Verifies:
        - Backend list_runs() is called
        - Response data is stored in results_data
        - RunRecord properties are accessible
        """
        backend = _make_mock_backend(runs=[mock_run_record])

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        with patch.object(ResultsTab, "create_backend", return_value=backend):
            async with app.run_test() as _:
                tab = app.query_one(ResultsTab)
                tab.refresh_data()

                # Verify data was loaded
                assert len(tab.results_data) == 1
                assert tab.results_data[0].id == mock_run_record.id
                assert backend.list_runs.called

    @pytest.mark.asyncio
    async def test_refresh_data_with_multiple_runs(
        self, cli_config, mock_run_record, mock_run_record_2
    ):
        """
        Test loading multiple runs.

        Verifies that multiple RunRecord objects are stored correctly.
        """
        backend = _make_mock_backend(runs=[mock_run_record, mock_run_record_2])

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        with patch.object(ResultsTab, "create_backend", return_value=backend):
            async with app.run_test() as _:
                tab = app.query_one(ResultsTab)
                tab.refresh_data()

                assert len(tab.results_data) == 2

    @pytest.mark.asyncio
    async def test_refresh_data_handles_empty_response(self, cli_config):
        """
        Test handling empty results.

        When the backend returns no runs (new user, no attacks yet),
        the widget should show an appropriate empty state.
        """
        backend = _make_mock_backend(runs=[])

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        with patch.object(ResultsTab, "create_backend", return_value=backend):
            async with app.run_test() as _:
                tab = app.query_one(ResultsTab)
                tab.refresh_data()

                assert len(tab.results_data) == 0

    @pytest.mark.asyncio
    async def test_refresh_data_handles_auth_error(self, cli_config):
        """
        Test handling authentication error from backend.

        When the API key is invalid, the backend raises an exception
        and the widget should not crash.
        """
        backend = _make_mock_backend(
            raise_on_list_runs=Exception("401 authentication failed")
        )

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        with patch.object(ResultsTab, "create_backend", return_value=backend):
            async with app.run_test() as _:
                tab = app.query_one(ResultsTab)
                tab.refresh_data()

                # Should show empty state, not crash
                assert len(tab.results_data) == 0

    @pytest.mark.asyncio
    async def test_refresh_data_handles_forbidden_error(self, cli_config):
        """
        Test handling forbidden error from backend.

        When the user doesn't have permission to view runs,
        the widget should handle it gracefully.
        """
        backend = _make_mock_backend(raise_on_list_runs=Exception("403 forbidden"))

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        with patch.object(ResultsTab, "create_backend", return_value=backend):
            async with app.run_test() as _:
                tab = app.query_one(ResultsTab)
                tab.refresh_data()

                assert len(tab.results_data) == 0

    @pytest.mark.asyncio
    async def test_refresh_data_handles_timeout(self, cli_config):
        """
        Test timeout handling during refresh.

        Network timeouts should be caught and displayed to user
        with a helpful message, not crash the app.
        """
        backend = _make_mock_backend(
            raise_on_list_runs=httpx.TimeoutException("Connection timeout")
        )

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        with patch.object(ResultsTab, "create_backend", return_value=backend):
            async with app.run_test() as _:
                tab = app.query_one(ResultsTab)
                tab.refresh_data()

                # Should not crash
                assert len(tab.results_data) == 0

    @pytest.mark.asyncio
    async def test_refresh_data_handles_generic_exception(self, cli_config):
        """
        Test generic exception handling.

        Any unexpected error should be caught and logged,
        not crash the entire TUI.
        """
        backend = _make_mock_backend(
            raise_on_list_runs=Exception("Unexpected network error")
        )

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        with patch.object(ResultsTab, "create_backend", return_value=backend):
            async with app.run_test() as _:
                tab = app.query_one(ResultsTab)
                tab.refresh_data()

                # Should handle gracefully
                assert len(tab.results_data) == 0

    @pytest.mark.asyncio
    async def test_refresh_data_without_api_key(self, cli_config):
        """
        Test refresh when API key is not configured (uses LocalBackend).

        When no API key is set, create_backend() returns a LocalBackend.
        We mock it to isolate the test from any local SQLite state.
        """
        cli_config.api_key = None
        backend = _make_mock_backend(runs=[])

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        with patch.object(ResultsTab, "create_backend", return_value=backend):
            async with app.run_test() as _:
                tab = app.query_one(ResultsTab)
                tab.refresh_data()

                assert len(tab.results_data) == 0

    @pytest.mark.asyncio
    async def test_refresh_data_calls_backend(self, cli_config, mock_run_record):
        """
        Test that refresh_data invokes the backend correctly.

        Verifies list_runs is called and the backend is exercised.
        """
        backend = _make_mock_backend(runs=[mock_run_record])

        class TestApp(App):
            def compose(self):
                yield ResultsTab(cli_config)

        app = TestApp()
        with patch.object(ResultsTab, "create_backend", return_value=backend):
            async with app.run_test() as _:
                tab = app.query_one(ResultsTab)
                tab.refresh_data()

                assert backend.list_runs.called
