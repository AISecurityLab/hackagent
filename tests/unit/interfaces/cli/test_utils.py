# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for CLI utilities and helper functions.
"""

from unittest.mock import patch
import pytest
from hackagent.interfaces.cli.utils import (
    display_error,
    display_info,
    display_success,
    display_warning,
    handle_errors,
)

# Import the new utils functions for testing


class TestErrorHandling:
    """Test error handling utilities"""

    def test_handle_errors_decorator_success(self):
        """Test error handler allows successful function execution"""

        @handle_errors
        def successful_function():
            return "success"

        result = successful_function()
        assert result == "success"

    def test_handle_errors_decorator_handles_exception(self):
        """Test error handler catches and formats exceptions"""
        import click

        @handle_errors
        def failing_function():
            raise ValueError("Test error message")

        # The decorator raises ClickException, not SystemExit
        with pytest.raises(click.ClickException):
            failing_function()

    def test_an_api_error_is_reported_as_one(self):
        """ApiError is a HackAgentError, so its handler must come first."""
        import click

        from hackagent.core.errors import ApiError

        @handle_errors
        def failing_function():
            raise ApiError("server said no")

        with pytest.raises(click.ClickException) as raised:
            failing_function()

        assert raised.value.format_message() == "API error: server said no"

    def test_a_failure_is_said_once_as_every_failure_is(self, capsys):
        """``✗ message``, and not Click's ``Error:`` after a line of ours."""
        import click

        @handle_errors
        def failing_function():
            raise ValueError("no such model")

        with pytest.raises(click.ClickException) as raised:
            failing_function()
        raised.value.show()

        err = capsys.readouterr().err
        assert err.strip() == "✗ no such model"

    def test_handle_errors_debug_mode(self):
        """Test error handler shows traceback in debug mode"""
        import click

        @handle_errors
        def failing_function():
            raise ValueError("Test error")

        with patch.dict("os.environ", {"HACKAGENT_DEBUG": "1"}):
            # In debug mode, full traceback should be shown
            with pytest.raises(click.ClickException):
                failing_function()

    def test_handle_errors_production_mode(self):
        """Test error handler hides traceback in production"""
        import click

        @handle_errors
        def failing_function():
            raise ValueError("Test error")

        with patch.dict("os.environ", {}, clear=True):
            # In production, only error message should be shown
            with pytest.raises(click.ClickException):
                failing_function()


class TestOutputFormatting:
    """Test output formatting functions"""

    def test_display_success_message(self):
        """Test success message display"""

        # Should not raise an error
        display_success("Test success message")

    def test_display_warning_message(self):
        """Test warning message display"""

        # Should not raise an error
        display_warning("Test warning message")

    def test_display_error_message(self):
        """Test error message display"""

        # Should not raise an error
        display_error("Test error message")

    def test_display_info_message(self):
        """Test info message display"""

        # Should not raise an error
        display_info("Test info message")
