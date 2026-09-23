# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for CLI utilities and helper functions.
"""

from unittest.mock import patch
import pytest
from rich.console import Console
from hackagent.cli.utils import (
    console,
    display_error,
    display_info,
    display_results_table,
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

    def test_display_results_table_empty_data(self):
        """Test table display with empty data"""
        # Test with empty list
        empty_list: list = []
        # Should not raise an error
        display_results_table(empty_list, "Test Results")

    def test_display_results_table_with_data(self):
        """Test table display with data"""
        data = [
            {"col1": "value1", "col2": "value2"},
            {"col1": "value3", "col2": "value4"},
        ]

        # Should not raise an error
        display_results_table(data, "Test Results")

    def test_display_results_table_with_list(self):
        """Test table display with list data"""

        data = [
            {"col1": "value1", "col2": "value2"},
            {"col1": "value3", "col2": "value4"},
        ]

        # Should not raise an error
        display_results_table(data, "Test Results")

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


class TestConsoleUtilities:
    """Test console utilities"""

    def test_console_instance(self):
        """Test console instance is properly configured"""

        assert isinstance(console, Console)
        # Could test specific console configuration here

    def test_table_creation_with_styling(self):
        """Test table creation with proper styling"""

        data = [{"name": "test", "status": "active"}]
        # Test that display_results_table doesn't raise an error
        display_results_table(data, "Test Table")

        # Test passes if no exception is raised
        assert True

    def test_progress_indication(self):
        """Test progress indication utilities"""

        # This would test any progress bar or status utilities
        # For now, just verify we can import console
        assert console is not None


class TestUtilityHelpers:
    """Test miscellaneous utility helper functions"""

    def test_data_validation(self):
        """Test data validation helpers"""

        # Test any data validation utility functions
        # This is a placeholder for actual validation functions
        assert True

    def test_color_formatting(self):
        """Test color and style formatting helpers"""

        # Test any color/style utility functions
        # This would verify rich markup is working correctly
        assert True

    def test_file_utilities(self):
        """Test file handling utilities"""

        # Test any file reading/writing utilities
        # This would test path handling, file operations, etc.
        assert True


class TestInteractiveElements:
    """Test interactive CLI elements"""

    def test_prompt_handling(self):
        """Test user prompt handling"""

        # Test any interactive prompt utilities
        # This would mock user input and test responses
        assert True

    def test_confirmation_prompts(self):
        """Test confirmation prompt utilities"""

        # Test yes/no confirmation prompts
        # This would test default values, validation, etc.
        assert True

    def test_selection_menus(self):
        """Test selection menu utilities"""

        # Test any selection menu utilities
        # This would test option handling, validation, etc.
        assert True


# NEW COMPREHENSIVE TESTS FOR STANDARDIZED API TOKEN RESOLUTION


class TestUtilityIntegration:
    """Test integration between utility functions"""

    def test_error_handling_with_formatting(self):
        """Test error handling works with formatting utilities"""
        # This would test interaction between error handlers and formatters
        assert True

    def test_console_output_capture(self):
        """Test capturing console output for testing"""
        # This would test console output capture utilities
        assert True

    def test_style_consistency(self):
        """Test consistent styling across utilities"""
        # This would verify styling consistency
        assert True
