# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the `hackagent eval chain` command."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from hackagent.cli.commands.attack import chain as chain_mod
from hackagent.cli.commands.attack.chain import chain


class TestChainCommand(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        splash = patch("hackagent.utils.display_hackagent_splash")
        splash.start()
        self.addCleanup(splash.stop)

    def _config_file(self, payload, name="chain.json"):
        path = Path(self.tmp.name) / name
        path.write_text(
            json.dumps(payload) if not isinstance(payload, str) else payload
        )
        return str(path)

    def _cli_config(self):
        config = MagicMock()
        config.api_key = "hk_key"
        config.base_url = "https://api.hackagent.dev"
        return config

    def _invoke(self, args, agent=None, cli_config=None):
        cli_config = cli_config or self._cli_config()
        agent = agent if agent is not None else MagicMock()
        with (
            patch.object(chain_mod, "HackAgent", return_value=agent) as agent_cls,
            patch.object(chain_mod, "_display_attack_results") as display,
        ):
            result = self.runner.invoke(chain, args, obj={"config": cli_config})
        return result, agent, agent_cls, display

    def _base_args(self, config_file, *extra):
        return [
            "--agent-name",
            "target-bot",
            "--endpoint",
            "http://localhost:8000",
            "--config-file",
            config_file,
            *extra,
        ]

    def test_chain_runs_every_configured_attack(self):
        path = self._config_file(
            {"attacks": [{"attack_type": "pair"}, {"attack_type": "tap"}]}
        )

        result, agent, agent_cls, display = self._invoke(
            self._base_args(path, "--goals", "goal one, goal two", "--timeout", "77")
        )

        self.assertEqual(result.exit_code, 0, result.output)
        kwargs = agent.hack_chain.call_args.kwargs
        self.assertEqual(
            [step["attack_type"] for step in kwargs["attacks"]], ["pair", "tap"]
        )
        self.assertEqual(kwargs["goals"], ["goal one", "goal two"])
        self.assertEqual(kwargs["run_config_override"], {"timeout": 77})
        self.assertTrue(kwargs["fail_on_run_error"])
        display.assert_called_once()
        self.assertEqual(agent_cls.call_args.kwargs["api_key"], "hk_key")

    def test_goals_can_come_from_the_config_file(self):
        path = self._config_file(
            {"attacks": [{"attack_type": "pair"}], "goals": "single goal"}
        )

        result, agent, _, _ = self._invoke(self._base_args(path))

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(agent.hack_chain.call_args.kwargs["goals"], ["single goal"])

    def test_first_step_dataset_satisfies_the_goal_requirement(self):
        path = self._config_file(
            {"attacks": [{"attack_type": "pair", "dataset": {"preset": "advbench"}}]}
        )

        result, agent, _, _ = self._invoke(self._base_args(path))

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIsNone(agent.hack_chain.call_args.kwargs["goals"])

    def test_dry_run_stops_before_creating_an_agent(self):
        path = self._config_file({"attacks": [{"attack_type": "pair"}]})

        result, _, agent_cls, _ = self._invoke(
            self._base_args(path, "--goals", "g", "--dry-run")
        )

        self.assertEqual(result.exit_code, 0)
        agent_cls.assert_not_called()
        self.assertIn("Configuration validation passed", result.output)

    def test_missing_attacks_list_is_rejected(self):
        path = self._config_file({"goals": ["g"]})

        result, _, agent_cls, _ = self._invoke(self._base_args(path))

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("non-empty top-level 'attacks' list", result.output)
        agent_cls.assert_not_called()

    def test_steps_without_an_attack_type_are_rejected(self):
        path = self._config_file({"attacks": [{"dataset": {}}], "goals": ["g"]})

        result, _, _, _ = self._invoke(self._base_args(path))

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("attacks[0]", result.output)

    def test_missing_goal_source_is_rejected(self):
        path = self._config_file({"attacks": [{"attack_type": "pair"}]})

        result, _, _, _ = self._invoke(self._base_args(path))

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Provide --goals", result.output)

    def test_malformed_config_file_is_reported(self):
        path = self._config_file("{not json", name="broken.json")

        result, _, _, _ = self._invoke(self._base_args(path))

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Failed to load config file", result.output)

    def test_invalid_cli_configuration_short_circuits(self):
        path = self._config_file({"attacks": [{"attack_type": "pair"}]})
        cli_config = self._cli_config()
        cli_config.validate.side_effect = ValueError("API key is required")

        result, _, agent_cls, _ = self._invoke(
            self._base_args(path, "--goals", "g"), cli_config=cli_config
        )

        self.assertNotEqual(result.exit_code, 0)
        agent_cls.assert_not_called()

    def test_agent_initialisation_failure_is_wrapped(self):
        path = self._config_file({"attacks": [{"attack_type": "pair"}]})
        cli_config = self._cli_config()

        with patch.object(
            chain_mod, "HackAgent", side_effect=RuntimeError("bad endpoint")
        ):
            result = self.runner.invoke(
                chain,
                self._base_args(path, "--goals", "g"),
                obj={"config": cli_config},
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Failed to initialize agent", result.output)

    def test_chain_execution_failure_is_wrapped(self):
        path = self._config_file({"attacks": [{"attack_type": "pair"}]})
        agent = MagicMock()
        agent.hack_chain.side_effect = RuntimeError("target unreachable")

        result, _, _, _ = self._invoke(
            self._base_args(path, "--goals", "g"), agent=agent
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Attack chain execution failed", result.output)

    def test_guardrail_options_are_forwarded(self):
        path = self._config_file({"attacks": [{"attack_type": "pair"}]})

        _, _, agent_cls, _ = self._invoke(
            self._base_args(
                path,
                "--goals",
                "g",
                "--before-guardrail-name",
                "guard-in",
                "--after-guardrail-name",
                "guard-out",
                "--after-guardrail-type",
                "ollama",
            )
        )

        kwargs = agent_cls.call_args.kwargs
        self.assertEqual(kwargs["before_guardrail"]["identifier"], "guard-in")
        self.assertEqual(kwargs["after_guardrail"]["agent_type"], "ollama")

    def test_missing_config_file_is_rejected_by_click(self):
        result = self.runner.invoke(
            chain,
            self._base_args("/nonexistent/chain.json"),
            obj={"config": self._cli_config()},
        )

        self.assertEqual(result.exit_code, 2)


if __name__ == "__main__":
    unittest.main()
