# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for the ``hackagent claude`` CLI command (Claude Code red-team preset).

The command is a thin convenience wrapper that either opens the TUI pre-filled
or, with ``--no-tui``, drives a headless attack against a locally installed
Claude Code binary. These tests stub the binary check (``shutil.which``), the
TUI, and ``HackAgent`` so the command's own control flow — preflight, goal
resolution, dry-run, TUI launch, and headless execution — is exercised without
any subprocess, network, or interactive UI.
"""

import unittest
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from hackagent.cli.commands.claude import claude, DEFAULT_GOALS


def _config():
    cfg = MagicMock()
    cfg.api_key = "k"
    cfg.base_url = "https://api.hackagent.dev"
    cfg.validate.return_value = None
    return cfg


def _invoke(args, **kwargs):
    return CliRunner().invoke(claude, args, obj={"config": _config()}, **kwargs)


class TestClaudePreflight(unittest.TestCase):
    @patch("hackagent.cli.commands.claude.shutil.which", return_value="/usr/bin/claude")
    @patch("hackagent.cli.commands.claude.HackAgent")
    def test_dry_run_validates_without_running(self, mock_agent, _which):
        result = _invoke(["--no-tui", "--dry-run"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("validation passed", result.output)
        mock_agent.assert_not_called()

    @patch("hackagent.cli.commands.claude.shutil.which", return_value=None)
    def test_missing_binary_headless_run_exits_nonzero(self, _which):
        # A real (non-dry-run) headless run with no binary must fail fast.
        result = _invoke(["--no-tui"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not on PATH", result.output)

    @patch("hackagent.cli.commands.claude.shutil.which", return_value=None)
    def test_skip_preflight_bypasses_binary_check(self, _which):
        # With --skip-preflight the missing-binary guidance is never shown and a
        # dry-run still validates.
        result = _invoke(["--no-tui", "--dry-run", "--skip-preflight"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertNotIn("not on PATH", result.output)
        self.assertIn("validation passed", result.output)


class TestClaudeHeadlessRun(unittest.TestCase):
    @patch("hackagent.cli.commands.claude.shutil.which", return_value="/usr/bin/claude")
    @patch("hackagent.cli.commands.claude.HackAgent")
    def test_headless_run_executes_attack(self, mock_agent, _which):
        instance = mock_agent.return_value
        instance.hack.return_value = [{"asr": 0.5}]

        result = _invoke(["--no-tui"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("completed successfully", result.output)

        mock_agent.assert_called_once()
        instance.hack.assert_called_once()
        attack_config = instance.hack.call_args.kwargs["attack_config"]
        self.assertEqual(attack_config["attack_type"], "flipattack")
        self.assertEqual(attack_config["goals"], list(DEFAULT_GOALS))

    @patch("hackagent.cli.commands.claude.shutil.which", return_value="/usr/bin/claude")
    @patch("hackagent.cli.commands.claude.HackAgent")
    def test_headless_run_failure_is_reported(self, mock_agent, _which):
        mock_agent.return_value.hack.side_effect = RuntimeError("boom")
        result = _invoke(["--no-tui"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Attack failed", result.output)

    @patch("hackagent.cli.commands.claude.shutil.which", return_value="/usr/bin/claude")
    @patch("hackagent.cli.commands.claude.HackAgent")
    def test_agent_init_failure_is_reported(self, mock_agent, _which):
        mock_agent.side_effect = RuntimeError("no creds")
        result = _invoke(["--no-tui"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Failed to initialize agent", result.output)

    @patch("hackagent.cli.commands.claude.shutil.which", return_value="/usr/bin/claude")
    @patch("hackagent.cli.commands.claude.HackAgent")
    def test_custom_goals_and_attack_type_override_defaults(self, mock_agent, _which):
        mock_agent.return_value.hack.return_value = []
        result = _invoke(
            [
                "--no-tui",
                "--goals",
                "g1,g2",
                "--attack-type",
                "pair",
                "--model",
                "sonnet",
            ]
        )
        self.assertEqual(result.exit_code, 0, result.output)
        attack_config = mock_agent.return_value.hack.call_args.kwargs["attack_config"]
        self.assertEqual(attack_config["attack_type"], "pair")
        self.assertEqual(attack_config["goals"], ["g1", "g2"])
        # Model flows through to the adapter operational config.
        op_config = mock_agent.call_args.kwargs["adapter_operational_config"]
        self.assertEqual(op_config["name"], "sonnet")


class TestClaudeTuiPath(unittest.TestCase):
    @patch("hackagent.cli.commands.claude.shutil.which", return_value="/usr/bin/claude")
    @patch("hackagent.cli.tui.HackAgentTUI")
    def test_default_path_launches_tui_prefilled(self, mock_tui, _which):
        result = _invoke([])  # no --no-tui → TUI is the default
        self.assertEqual(result.exit_code, 0, result.output)
        mock_tui.assert_called_once()
        mock_tui.return_value.run.assert_called_once()
        # Preset values are passed into the Attacks tab.
        initial_data = mock_tui.call_args.kwargs["initial_data"]
        self.assertEqual(initial_data["agent_type"], "claude-code")
        self.assertEqual(initial_data["attack_type"], "flipattack")
        self.assertEqual(initial_data["endpoint"], "")


if __name__ == "__main__":
    unittest.main()
