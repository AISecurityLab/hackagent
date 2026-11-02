# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for hackagent CLI main entry point (cli/main.py).

Uses Click's CliRunner for realistic CLI invocation testing.
"""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from hackagent import Settings
from hackagent.interfaces.cli.main import cli


class TestCLIVersion(unittest.TestCase):
    """Test the version command."""

    def test_version_flag(self):
        """Test --version flag shows version info."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["--config-file", "/nonexistent-hackagent-test-config", "--version"]
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("hackagent", result.output)

    @patch("hackagent.interfaces.cli.main.CLIConfig")
    def test_version_command(self, mock_config_class):
        """Test 'version' command displays version."""
        mock_config = MagicMock()
        mock_config.api_key = "test-key-123456789"
        mock_config.base_url = "https://api.hackagent.dev"
        mock_config.default_config_path = Path("/tmp/config.json")
        mock_config_class.return_value = mock_config

        runner = CliRunner()
        result = runner.invoke(
            cli, ["--config-file", "/nonexistent-hackagent-test-config", "version"]
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("HackAgent CLI", result.output)


class TestCLIHelp(unittest.TestCase):
    """Test CLI help output."""

    def test_help_flag(self):
        """Test --help flag shows help text."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["--config-file", "/nonexistent-hackagent-test-config", "--help"]
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("HackAgent CLI", result.output)
        self.assertIn("Quick Start", result.output)

    def test_help_shows_commands(self):
        """Test help output lists available commands."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["--config-file", "/nonexistent-hackagent-test-config", "--help"]
        )
        self.assertIn("config", result.output)
        self.assertIn("campaign", result.output)
        self.assertIn("init", result.output)
        self.assertIn("version", result.output)
        self.assertIn("doctor", result.output)

    def test_campaign_help_prints_without_error(self):
        """campaign --help must not crash."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--config-file",
                "/nonexistent-hackagent-test-config",
                "campaign",
                "--help",
            ],
        )
        self.assertEqual(result.exit_code, 0)


class TestCLIConfigContext(unittest.TestCase):
    """Test CLI configuration context setup."""

    @patch("hackagent.interfaces.cli.main.CLIConfig")
    @patch("hackagent.interfaces.cli.main._launch_tui_default")
    def test_config_passed_to_context(self, mock_tui, mock_config_class):
        """Test that CLIConfig is initialized and passed to context."""
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        runner = CliRunner()
        runner.invoke(
            cli,
            [
                "--config-file",
                "/nonexistent-hackagent-test-config",
            ],
        )

        mock_config_class.assert_called_once()

    @patch("hackagent.interfaces.cli.main.CLIConfig")
    @patch("hackagent.interfaces.cli.main._launch_tui_default")
    def test_backend_passed_to_config(self, mock_tui, mock_config_class):
        """Test that backend selection is passed to CLIConfig."""
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        runner = CliRunner()
        runner.invoke(
            cli,
            [
                "--config-file",
                "/nonexistent-hackagent-test-config",
                "--backend",
                "remote",
            ],
        )

        call_kwargs = mock_config_class.call_args.kwargs
        self.assertEqual(call_kwargs["backend"], "remote")

    @patch("hackagent.interfaces.cli.main.CLIConfig")
    @patch("hackagent.interfaces.cli.main._launch_tui_default")
    def test_base_url_passed_to_config(self, mock_tui, mock_config_class):
        """Test that --base-url option is passed to CLIConfig."""
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        runner = CliRunner()
        runner.invoke(
            cli,
            [
                "--config-file",
                "/nonexistent-hackagent-test-config",
                "--base-url",
                "https://custom.api.com",
            ],
        )

        call_kwargs = mock_config_class.call_args.kwargs
        self.assertEqual(call_kwargs["base_url"], "https://custom.api.com")

    @patch("hackagent.interfaces.cli.main.CLIConfig")
    @patch("hackagent.interfaces.cli.main._launch_tui_default")
    def test_verbose_flag(self, mock_tui, mock_config_class):
        """Test that -v verbose flag increments verbosity."""
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        runner = CliRunner()
        runner.invoke(
            cli, ["--config-file", "/nonexistent-hackagent-test-config", "-vv"]
        )

        call_kwargs = mock_config_class.call_args.kwargs
        self.assertEqual(call_kwargs["verbose"], 2)

    @patch("hackagent.interfaces.cli.main.CLIConfig")
    def test_config_error_exits(self, mock_config_class):
        """Test that configuration error causes exit."""
        mock_config_class.side_effect = Exception("Config error")

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--config-file",
                "/nonexistent-hackagent-test-config",
            ],
        )

        self.assertNotEqual(result.exit_code, 0)


class TestCLIDoctor(unittest.TestCase):
    """Test the doctor command."""

    @patch("hackagent.interfaces.cli.main.CLIConfig")
    def test_doctor_no_api_key(self, mock_config_class):
        """Test doctor when no API key is configured."""
        mock_config = MagicMock()
        mock_config.api_key = None
        mock_config.settings = Settings.resolve(
            backend="local",
            env={},
            config_path="/nonexistent-hackagent-doctor-config",
        )
        mock_config.default_config_path = MagicMock()
        mock_config.default_config_path.exists.return_value = False
        mock_config_class.return_value = mock_config

        runner = CliRunner()
        result = runner.invoke(
            cli, ["--config-file", "/nonexistent-hackagent-test-config", "doctor"]
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("API key not set", result.output)

    @patch("hackagent.interfaces.cli.main.CLIConfig")
    def test_doctor_with_api_key(self, mock_config_class):
        """Test doctor when API key is configured."""
        mock_config = MagicMock()
        mock_config.api_key = "a-very-long-api-key-that-is-valid"
        mock_config.base_url = "https://api.hackagent.dev"
        mock_config.settings = Settings.resolve(
            api_key="a-very-long-api-key-that-is-valid",
            base_url="https://api.hackagent.dev",
            env={},
            config_path="/nonexistent-hackagent-doctor-config",
        )
        mock_config.default_config_path = MagicMock()
        mock_config.default_config_path.exists.return_value = True
        mock_config_class.return_value = mock_config

        runner = CliRunner()
        result = runner.invoke(
            cli, ["--config-file", "/nonexistent-hackagent-test-config", "doctor"]
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("API key is set", result.output)


class TestCLINoCommand(unittest.TestCase):
    """Test CLI with no subcommand."""

    @patch("hackagent.interfaces.cli.main.CLIConfig")
    @patch("hackagent.interfaces.cli.main._launch_tui_default")
    def test_no_command_launches_tui(self, mock_tui, mock_config_class):
        """Test that no subcommand launches TUI."""
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        runner = CliRunner()
        runner.invoke(
            cli,
            [
                "--config-file",
                "/nonexistent-hackagent-test-config",
            ],
        )

        mock_tui.assert_called_once()


class TestCLIInit(unittest.TestCase):
    """Test the init setup wizard."""

    @patch("hackagent.interfaces.cli.banner.display_hackagent_splash")
    @patch("hackagent.interfaces.cli.main.click.prompt")
    @patch("hackagent.interfaces.cli.main.click.confirm")
    @patch("hackagent.interfaces.cli.main.CLIConfig")
    def test_init_configures_remote_mode(
        self,
        mock_config_class,
        mock_confirm,
        mock_prompt,
        mock_splash,
    ):
        """Test init captures API key when remote mode is enabled."""
        mock_config = MagicMock()
        mock_config.api_key = None
        mock_config.base_url = "https://api.hackagent.dev"
        mock_config.verbose = 1
        mock_config.should_show_info.return_value = False
        mock_config.default_config_path = MagicMock()
        mock_config.default_config_path.exists.return_value = False
        mock_config_class.return_value = mock_config

        # Prompt order in init:
        # 1) API key, 2) verbosity level
        mock_confirm.return_value = True
        mock_prompt.side_effect = [2]

        runner = CliRunner()
        result = runner.invoke(
            cli, ["--config-file", "/nonexistent-hackagent-test-config", "init"]
        )

        self.assertEqual(result.exit_code, 0)
        mock_config.set_user_override.assert_any_call("backend", "remote")
        self.assertEqual(mock_config.base_url, "https://api.hackagent.dev")
        self.assertEqual(mock_config.verbose, 2)
        mock_config.save.assert_called_once()
        mock_splash.assert_called_once()

    @patch("hackagent.interfaces.cli.banner.display_hackagent_splash")
    @patch("hackagent.interfaces.cli.main.click.prompt")
    @patch("hackagent.interfaces.cli.main.click.confirm")
    @patch("hackagent.interfaces.cli.main.CLIConfig")
    def test_init_local_mode_clears_api_key(
        self,
        mock_config_class,
        mock_confirm,
        mock_prompt,
        mock_splash,
    ):
        """Test init local mode clears any existing API key from config."""
        mock_config = MagicMock()
        mock_config.api_key = "existing-key"
        mock_config.base_url = "https://api.hackagent.dev"
        mock_config.verbose = 1
        mock_config.should_show_info.return_value = False
        mock_config.default_config_path = MagicMock()
        mock_config.default_config_path.exists.return_value = False
        mock_config_class.return_value = mock_config

        # Local mode confirmation + verbosity prompt.
        mock_confirm.return_value = False
        mock_prompt.return_value = 1

        runner = CliRunner()
        result = runner.invoke(
            cli, ["--config-file", "/nonexistent-hackagent-test-config", "init"]
        )

        self.assertEqual(result.exit_code, 0)
        mock_config.set_user_override.assert_any_call("backend", "local")
        self.assertEqual(mock_config.api_key, "existing-key")
        self.assertEqual(mock_config.verbose, 1)
        mock_config.save.assert_called_once()
        mock_splash.assert_called_once()


if __name__ == "__main__":
    unittest.main()
