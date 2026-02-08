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

"""Tests for hackagent CLI main entry point (cli/main.py).

Uses Click's CliRunner for realistic CLI invocation testing.
"""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from hackagent.cli.main import cli


class TestCLIVersion(unittest.TestCase):
    """Test the version command."""

    def test_version_flag(self):
        """Test --version flag shows version info."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("hackagent", result.output)

    @patch("hackagent.cli.main.CLIConfig")
    def test_version_command(self, mock_config_class):
        """Test 'version' command displays version."""
        mock_config = MagicMock()
        mock_config.api_key = "test-key-123456789"
        mock_config.base_url = "https://api.hackagent.dev"
        mock_config.default_config_path = Path("/tmp/config.json")
        mock_config_class.return_value = mock_config

        runner = CliRunner()
        result = runner.invoke(cli, ["version"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("HackAgent CLI", result.output)


class TestCLIHelp(unittest.TestCase):
    """Test CLI help output."""

    def test_help_flag(self):
        """Test --help flag shows help text."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("HackAgent CLI", result.output)
        self.assertIn("Common Usage", result.output)

    def test_help_shows_commands(self):
        """Test help output lists available commands."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        self.assertIn("config", result.output)
        self.assertIn("attack", result.output)
        self.assertIn("init", result.output)
        self.assertIn("version", result.output)
        self.assertIn("doctor", result.output)


class TestCLIConfigContext(unittest.TestCase):
    """Test CLI configuration context setup."""

    @patch("hackagent.cli.main.CLIConfig")
    @patch("hackagent.cli.main._launch_tui_default")
    def test_config_passed_to_context(self, mock_tui, mock_config_class):
        """Test that CLIConfig is initialized and passed to context."""
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        runner = CliRunner()
        runner.invoke(cli, [])

        mock_config_class.assert_called_once()

    @patch("hackagent.cli.main.CLIConfig")
    @patch("hackagent.cli.main._launch_tui_default")
    def test_api_key_passed_to_config(self, mock_tui, mock_config_class):
        """Test that --api-key option is passed to CLIConfig."""
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        runner = CliRunner()
        runner.invoke(cli, ["--api-key", "my-test-key"])

        call_kwargs = mock_config_class.call_args.kwargs
        self.assertEqual(call_kwargs["api_key"], "my-test-key")

    @patch("hackagent.cli.main.CLIConfig")
    @patch("hackagent.cli.main._launch_tui_default")
    def test_base_url_passed_to_config(self, mock_tui, mock_config_class):
        """Test that --base-url option is passed to CLIConfig."""
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        runner = CliRunner()
        runner.invoke(cli, ["--base-url", "https://custom.api.com"])

        call_kwargs = mock_config_class.call_args.kwargs
        self.assertEqual(call_kwargs["base_url"], "https://custom.api.com")

    @patch("hackagent.cli.main.CLIConfig")
    @patch("hackagent.cli.main._launch_tui_default")
    def test_verbose_flag(self, mock_tui, mock_config_class):
        """Test that -v verbose flag increments verbosity."""
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        runner = CliRunner()
        runner.invoke(cli, ["-vv"])

        call_kwargs = mock_config_class.call_args.kwargs
        self.assertEqual(call_kwargs["verbose"], 2)

    @patch("hackagent.cli.main.CLIConfig")
    @patch("hackagent.cli.main._launch_tui_default")
    def test_output_format_passed(self, mock_tui, mock_config_class):
        """Test that --output-format is passed to CLIConfig."""
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        runner = CliRunner()
        runner.invoke(cli, ["--output-format", "json"])

        call_kwargs = mock_config_class.call_args.kwargs
        self.assertEqual(call_kwargs["output_format"], "json")

    @patch("hackagent.cli.main.CLIConfig")
    def test_config_error_exits(self, mock_config_class):
        """Test that configuration error causes exit."""
        mock_config_class.side_effect = Exception("Config error")

        runner = CliRunner()
        result = runner.invoke(cli, [])

        self.assertNotEqual(result.exit_code, 0)


class TestCLIDoctor(unittest.TestCase):
    """Test the doctor command."""

    @patch("hackagent.cli.main.CLIConfig")
    def test_doctor_no_api_key(self, mock_config_class):
        """Test doctor when no API key is configured."""
        mock_config = MagicMock()
        mock_config.api_key = None
        mock_config.default_config_path = MagicMock()
        mock_config.default_config_path.exists.return_value = False
        mock_config_class.return_value = mock_config

        runner = CliRunner()
        result = runner.invoke(cli, ["doctor"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("API key not set", result.output)

    @patch("hackagent.cli.main.CLIConfig")
    def test_doctor_with_api_key(self, mock_config_class):
        """Test doctor when API key is configured."""
        mock_config = MagicMock()
        mock_config.api_key = "a-very-long-api-key-that-is-valid"
        mock_config.base_url = "https://api.hackagent.dev"
        mock_config.default_config_path = MagicMock()
        mock_config.default_config_path.exists.return_value = True
        mock_config_class.return_value = mock_config

        # Mock the API call
        with patch("hackagent.cli.main.agent_list", create=True) as mock_agent:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_agent.sync_detailed.return_value = mock_response

            runner = CliRunner()
            result = runner.invoke(cli, ["doctor"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("API key is set", result.output)


class TestCLINoCommand(unittest.TestCase):
    """Test CLI with no subcommand."""

    @patch("hackagent.cli.main.CLIConfig")
    @patch("hackagent.cli.main._launch_tui_default")
    def test_no_command_launches_tui(self, mock_tui, mock_config_class):
        """Test that no subcommand launches TUI."""
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        runner = CliRunner()
        runner.invoke(cli, [])

        mock_tui.assert_called_once()


if __name__ == "__main__":
    unittest.main()
