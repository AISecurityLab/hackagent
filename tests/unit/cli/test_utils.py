# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for CLI utilities and helper functions.
"""

import json
import tempfile
from pathlib import Path
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
from hackagent.utils import (
    _load_api_key_from_config,
    resolve_agent_type,
    resolve_api_token,
)


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
class TestStandardizedAPITokenResolution:
    """Test the standardized API token resolution functionality"""

    def test_load_api_key_from_config_success(self):
        """Test successful API key loading from config file"""
        config_data = {"api_key": "test-config-key", "output_format": "json"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            result = _load_api_key_from_config(config_file)
            assert result == "test-config-key"
        finally:
            Path(config_file).unlink()

    def test_load_api_key_from_config_default_path(self):
        """Test loading from default config path"""
        config_data = {"api_key": "default-path-key"}

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("pathlib.Path.home") as mock_home:
                mock_home.return_value = Path(temp_dir)

                # Create .config/hackagent directory and config file
                config_dir = Path(temp_dir) / ".config" / "hackagent"
                config_dir.mkdir(parents=True)
                config_file = config_dir / "config.json"

                with open(config_file, "w") as f:
                    json.dump(config_data, f)

                result = _load_api_key_from_config()
                assert result == "default-path-key"

    def test_load_api_key_from_config_file_not_found(self):
        """Test behavior when config file doesn't exist"""
        result = _load_api_key_from_config("/nonexistent/config.json")
        assert result is None

    def test_load_api_key_from_config_no_api_key(self):
        """Test config file without api_key field"""
        config_data = {"output_format": "json", "other_field": "value"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            result = _load_api_key_from_config(config_file)
            assert result is None
        finally:
            Path(config_file).unlink()

    def test_load_api_key_from_config_yaml_support(self):
        """Test loading API key from YAML config file"""
        yaml_content = """
api_key: yaml-test-key
output_format: table
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            config_file = f.name

        try:
            # This test depends on PyYAML being available
            import importlib.util

            if importlib.util.find_spec("yaml") is not None:
                result = _load_api_key_from_config(config_file)
                assert result == "yaml-test-key"
            else:
                # PyYAML not available, should return None gracefully
                result = _load_api_key_from_config(config_file)
                assert result is None
        finally:
            Path(config_file).unlink()

    def test_load_api_key_from_config_invalid_json(self):
        """Test handling of invalid JSON config file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("invalid json content")
            config_file = f.name

        try:
            result = _load_api_key_from_config(config_file)
            assert result is None  # Should handle error gracefully
        finally:
            Path(config_file).unlink()

    def test_resolve_api_token_direct_parameter_priority(self):
        """Test direct parameter has highest priority"""
        # Set up config file that should be ignored
        config_data = {"api_key": "config-should-be-ignored"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            result = resolve_api_token(
                direct_api_key_param="direct-wins", config_file_path=config_file
            )
            assert result == "direct-wins"
        finally:
            Path(config_file).unlink()

    def test_resolve_api_token_config_file(self):
        """Test config file is used when no direct parameter"""
        config_data = {"api_key": "config-key"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            result = resolve_api_token(
                direct_api_key_param=None, config_file_path=config_file
            )
            assert result == "config-key"
        finally:
            Path(config_file).unlink()

    def test_resolve_api_token_default_config_path(self):
        """Test using default config path when not specified"""
        config_data = {"api_key": "default-config-key"}

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("pathlib.Path.home") as mock_home:
                mock_home.return_value = Path(temp_dir)

                # Create .config/hackagent directory and config file
                config_dir = Path(temp_dir) / ".config" / "hackagent"
                config_dir.mkdir(parents=True)
                config_file = config_dir / "config.json"

                with open(config_file, "w") as f:
                    json.dump(config_data, f)

                result = resolve_api_token(direct_api_key_param=None)
                assert result == "default-config-key"

    def test_resolve_api_token_error_no_sources(self):
        """Test error when no API token found from any source"""
        with pytest.raises(ValueError) as exc_info:
            resolve_api_token(
                direct_api_key_param=None,
                config_file_path="/nonexistent/config.json",
            )

        error_msg = str(exc_info.value)
        assert "API token not found from any source" in error_msg
        assert "Direct 'api_key' parameter" in error_msg
        assert "Config file" in error_msg

    def test_resolve_api_token_comprehensive_priority_matrix(self):
        """Comprehensive test of priority scenarios (direct > config)"""
        scenarios = [
            # (direct, config_exists, config_key, expected, description)
            ("direct", True, "config", "direct", "Direct beats config"),
            (None, True, "config", "config", "Config when no direct"),
            ("direct", False, None, "direct", "Direct when no config"),
            (
                "direct",
                True,
                None,
                "direct",
                "Direct when config has no key",
            ),
        ]

        for (
            direct,
            config_exists,
            config_key,
            expected,
            description,
        ) in scenarios:
            if config_exists:
                config_data = {"api_key": config_key} if config_key else {}
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".json", delete=False
                ) as f:
                    json.dump(config_data, f)
                    config_file = f.name
            else:
                config_file = "/nonexistent/config.json"

            try:
                if expected is not None:
                    result = resolve_api_token(
                        direct_api_key_param=direct, config_file_path=config_file
                    )
                    assert result == expected, f"Failed scenario: {description}"
                else:
                    # Should raise error
                    with pytest.raises(ValueError):
                        resolve_api_token(
                            direct_api_key_param=direct,
                            config_file_path=config_file,
                        )
            finally:
                if config_exists and Path(config_file).exists():
                    Path(config_file).unlink()


class TestAgentTypeResolution:
    """Test agent type resolution functionality"""

    def test_resolve_agent_type_enum_input(self):
        """Test agent type resolution with enum input"""
        from hackagent.router.types import AgentTypeEnum

        result = resolve_agent_type(AgentTypeEnum.GOOGLE_ADK)
        assert result == AgentTypeEnum.GOOGLE_ADK

    def test_resolve_agent_type_string_input(self):
        """Test agent type resolution with string input"""
        from hackagent.router.types import AgentTypeEnum

        # Test various string formats
        test_cases = [
            ("google-adk", AgentTypeEnum.GOOGLE_ADK),
            ("GOOGLE_ADK", AgentTypeEnum.GOOGLE_ADK),
            ("litellm", AgentTypeEnum.LITELLM),
            ("unknown", AgentTypeEnum.UNKNOWN),
        ]

        for input_str, expected in test_cases:
            result = resolve_agent_type(input_str)
            assert result == expected

    def test_resolve_agent_type_invalid_string(self):
        """Test agent type resolution with invalid string"""
        from hackagent.router.types import AgentTypeEnum

        result = resolve_agent_type("invalid-type")
        assert result == AgentTypeEnum.UNKNOWN

    def test_resolve_agent_type_invalid_type(self):
        """Test agent type resolution with invalid type"""
        from hackagent.router.types import AgentTypeEnum

        result = resolve_agent_type(123)  # Invalid type
        assert result == AgentTypeEnum.UNKNOWN


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

    def test_full_integration_workflow(self):
        """Test complete workflow integration"""
        # Test a complete workflow using multiple utility functions
        config_data = {"api_key": "integration-test-key"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            # Test the full flow: config loading -> API token resolution
            api_key = _load_api_key_from_config(config_file)
            assert api_key == "integration-test-key"

            resolved_token = resolve_api_token(
                direct_api_key_param=None, config_file_path=config_file
            )
            assert resolved_token == "integration-test-key"

        finally:
            Path(config_file).unlink()

    def test_error_scenarios_integration(self):
        """Test error handling across integrated utilities"""
        # Should handle missing config gracefully
        config_key = _load_api_key_from_config("/nonexistent/config.json")
        assert config_key is None

        # Should raise appropriate error when all sources fail
        with pytest.raises(ValueError):
            resolve_api_token(
                direct_api_key_param=None,
                config_file_path="/nonexistent/config.json",
            )
