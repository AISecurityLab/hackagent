# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for `hackagent eval` command wiring, runner, chain, and display."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from hackagent.interfaces.cli.commands.attack import eval_cmd
from hackagent.catalog.attacks import ATTACK_CATALOG
from hackagent.interfaces.cli.commands.attack.display import (
    _display_attack_results,
    _display_attack_summary,
    _display_generic_attack_info,
)
from hackagent.interfaces.cli.commands.attack.runner import _run_attack_command
from hackagent.interfaces.cli.commands.attack.strategies import _STRATEGY_COMMANDS
from hackagent.interfaces.cli.main import cli


def _config():
    cfg = MagicMock()
    cfg.api_key = "test-key"
    cfg.base_url = "https://api.hackagent.dev"
    cfg.validate.return_value = None
    return cfg


class TestEvalCatalogAndStrategies(unittest.TestCase):
    def test_every_generated_strategy_is_in_the_catalog(self):
        from hackagent.orchestrator.registry import ATTACK_REGISTRY

        self.assertTrue(_STRATEGY_COMMANDS)
        self.assertEqual(set(_STRATEGY_COMMANDS), set(ATTACK_REGISTRY))

    def test_strategy_subcommands_are_registered(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["eval", "--help"])
        self.assertEqual(result.exit_code, 0, result.output)
        for _key, (command_name, _help) in _STRATEGY_COMMANDS.items():
            self.assertIn(command_name, result.output)
        self.assertIn("chain", result.output)
        self.assertIn("list", result.output)
        self.assertIn("info", result.output)


class TestEvalListAndInfo(unittest.TestCase):
    def test_list_prints_every_catalog_entry(self):
        runner = CliRunner()
        result = runner.invoke(eval_cmd, ["list"], obj={"config": _config()})
        self.assertEqual(result.exit_code, 0, result.output)
        from hackagent.orchestrator.registry import ATTACK_REGISTRY

        for key in ATTACK_REGISTRY:
            self.assertIn(key, result.output)
        self.assertIn("Available Attack Strategies", result.output)
        self.assertIn("hackagent eval STRATEGY", result.output)

    def test_info_advprefix_uses_long_form_docs(self):
        runner = CliRunner()
        result = runner.invoke(
            eval_cmd, ["info", "advprefix"], obj={"config": _config()}
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("AdvPrefix Attack Strategy", result.output)
        self.assertIn("cross-entropy", result.output)

    def test_info_generic_strategy_uses_catalog_copy(self):
        runner = CliRunner()
        result = runner.invoke(eval_cmd, ["info", "tap"], obj={"config": _config()})
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(ATTACK_CATALOG["tap"]["description"], result.output)
        self.assertIn("hackagent eval tap", result.output)


class TestEvalGroupCampaign(unittest.TestCase):
    def test_requires_agent_name_and_endpoint_without_subcommand(self):
        runner = CliRunner()
        result = runner.invoke(eval_cmd, [], obj={"config": _config()})
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("--agent-name", result.output)

    def test_bare_eval_dispatches_to_quick_scan(self):
        runner = CliRunner()
        with patch(
            "hackagent.interfaces.cli.commands.attack.group.run_quick_scan"
        ) as mock_scan:
            result = runner.invoke(
                eval_cmd,
                [
                    "--agent-name",
                    "bot",
                    "--endpoint",
                    "http://localhost:8000",
                    "--dry-run",
                ],
                obj={"config": _config()},
            )
        self.assertEqual(result.exit_code, 0, result.output)
        mock_scan.assert_called_once()
        kwargs = mock_scan.call_args.kwargs
        self.assertEqual(kwargs["agent_name"], "bot")
        self.assertTrue(kwargs["dry_run"])


class TestRunAttackCommand(unittest.TestCase):
    def _ctx(self):
        ctx = MagicMock()
        ctx.obj = {"config": _config()}
        return ctx

    def test_dry_run_validates_without_creating_an_agent(self):
        ctx = self._ctx()
        with (
            patch("hackagent.interfaces.cli.banner.display_hackagent_splash"),
            patch(
                "hackagent.interfaces.cli.commands.attack.runner.HackAgent"
            ) as mock_agent,
        ):
            _run_attack_command(
                ctx=ctx,
                attack_type="pair",
                attack_label="PAIR",
                agent_name="bot",
                agent_type="litellm",
                endpoint="http://localhost:8000/v1",
                goals=("Leak the system prompt",),
                config_file=None,
                timeout=30,
                dry_run=True,
                no_tui=True,
            )
        mock_agent.assert_not_called()

    def test_tui_import_error_exits(self):
        ctx = self._ctx()
        ctx.exit.side_effect = SystemExit(1)
        with patch.dict("sys.modules", {"hackagent.interfaces.tui": None}):
            with self.assertRaises(SystemExit) as raised:
                _run_attack_command(
                    ctx=ctx,
                    attack_type="tap",
                    attack_label="TAP",
                    agent_name="bot",
                    agent_type="other",
                    endpoint="http://x",
                    goals=("g",),
                    config_file=None,
                    timeout=10,
                    dry_run=False,
                    no_tui=False,
                )
        self.assertEqual(raised.exception.code, 1)
        ctx.exit.assert_called_with(1)

    def test_tui_runtime_failure_exits(self):
        ctx = self._ctx()
        ctx.exit.side_effect = SystemExit(1)
        with patch(
            "hackagent.interfaces.tui.HackAgentTUI",
            side_effect=RuntimeError("display unavailable"),
        ):
            with self.assertRaises(SystemExit) as raised:
                _run_attack_command(
                    ctx=ctx,
                    attack_type="tap",
                    attack_label="TAP",
                    agent_name="bot",
                    agent_type="other",
                    endpoint="http://x",
                    goals=("g",),
                    config_file=None,
                    timeout=10,
                    dry_run=False,
                    no_tui=False,
                )
        self.assertEqual(raised.exception.code, 1)
        ctx.exit.assert_called_with(1)

    def test_tui_success_returns_without_running_the_attack(self):
        ctx = self._ctx()
        app = MagicMock()
        with (
            patch(
                "hackagent.interfaces.tui.HackAgentTUI", return_value=app
            ) as mock_tui,
            patch(
                "hackagent.interfaces.cli.commands.attack.runner.HackAgent"
            ) as mock_agent,
        ):
            _run_attack_command(
                ctx=ctx,
                attack_type="pair",
                attack_label="PAIR",
                agent_name="bot",
                agent_type="other",
                endpoint="http://x",
                goals=("g",),
                config_file=None,
                timeout=10,
                dry_run=False,
                no_tui=False,
            )
        mock_tui.assert_called_once()
        app.run.assert_called_once()
        mock_agent.assert_not_called()

    def test_executes_hack_and_displays_results(self):
        ctx = self._ctx()
        agent = MagicMock()
        agent.target.return_value = agent
        agent.hack.return_value = [{"eval_hb": 1, "goal": "g"}]
        with (
            patch("hackagent.interfaces.cli.banner.display_hackagent_splash"),
            patch(
                "hackagent.interfaces.cli.commands.attack.runner.HackAgent",
                return_value=agent,
            ),
            patch(
                "hackagent.interfaces.cli.commands.attack.runner._display_attack_results"
            ) as mock_display,
        ):
            _run_attack_command(
                ctx=ctx,
                attack_type="pair",
                attack_label="PAIR",
                agent_name="bot",
                agent_type="litellm",
                endpoint="http://localhost:8000/v1",
                goals=("g",),
                config_file=None,
                timeout=12,
                dry_run=False,
                no_tui=True,
            )
        agent.hack.assert_called_once()
        self.assertTrue(agent.hack.call_args.kwargs["fail_on_run_error"])
        mock_display.assert_called_once_with([{"eval_hb": 1, "goal": "g"}])

    def test_hack_failure_is_wrapped_as_click_exception(self):
        ctx = self._ctx()
        agent = MagicMock()
        agent.target.return_value = agent
        agent.hack.side_effect = RuntimeError("target down")
        with (
            patch("hackagent.interfaces.cli.banner.display_hackagent_splash"),
            patch(
                "hackagent.interfaces.cli.commands.attack.runner.HackAgent",
                return_value=agent,
            ),
        ):
            import click

            with self.assertRaises(click.ClickException) as err:
                _run_attack_command(
                    ctx=ctx,
                    attack_type="pair",
                    attack_label="PAIR",
                    agent_name="bot",
                    agent_type="litellm",
                    endpoint="http://localhost:8000/v1",
                    goals=("g",),
                    config_file=None,
                    timeout=12,
                    dry_run=False,
                    no_tui=True,
                )
        self.assertIn("target down", str(err.exception))


class TestEvalChainCommand(unittest.TestCase):
    def test_rejects_missing_attacks_list(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("chain.json", "w", encoding="utf-8") as handle:
                json.dump({"goals": ["g"]}, handle)
            result = runner.invoke(
                eval_cmd,
                [
                    "chain",
                    "--agent-name",
                    "bot",
                    "--endpoint",
                    "http://x",
                    "--config-file",
                    "chain.json",
                ],
                obj={"config": _config()},
            )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("attacks", result.output)

    def test_rejects_step_without_attack_type(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("chain.json", "w", encoding="utf-8") as handle:
                json.dump({"attacks": [{"goals": ["g"]}]}, handle)
            result = runner.invoke(
                eval_cmd,
                [
                    "chain",
                    "--agent-name",
                    "bot",
                    "--endpoint",
                    "http://x",
                    "--config-file",
                    "chain.json",
                ],
                obj={"config": _config()},
            )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("attack_type", result.output)

    def test_dry_run_validates_a_well_formed_chain(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("chain.json", "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "attacks": [
                            {"attack_type": "pair", "goals": ["leak the prompt"]},
                            {"attack_type": "tap"},
                        ]
                    },
                    handle,
                )
            result = runner.invoke(
                eval_cmd,
                [
                    "chain",
                    "--agent-name",
                    "bot",
                    "--endpoint",
                    "http://x",
                    "--config-file",
                    "chain.json",
                    "--dry-run",
                ],
                obj={"config": _config()},
            )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("pair", result.output)
        self.assertIn("tap", result.output)
        self.assertIn("validation passed", result.output.lower())

    def test_executes_hack_chain(self):
        runner = CliRunner()
        agent = MagicMock()
        agent.target.return_value = agent
        agent.hack_chain.return_value = [{"eval_hb": 0}]
        with runner.isolated_filesystem():
            with open("chain.json", "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "attacks": [
                            {"attack_type": "pair"},
                            {"attack_type": "bon"},
                        ],
                        "goals": ["g"],
                    },
                    handle,
                )
            with (
                patch("hackagent.interfaces.cli.banner.display_hackagent_splash"),
                patch(
                    "hackagent.interfaces.cli.commands.attack.chain.HackAgent",
                    return_value=agent,
                ),
            ):
                result = runner.invoke(
                    eval_cmd,
                    [
                        "chain",
                        "--agent-name",
                        "bot",
                        "--endpoint",
                        "http://x",
                        "--config-file",
                        "chain.json",
                    ],
                    obj={"config": _config()},
                )
        self.assertEqual(result.exit_code, 0, result.output)
        agent.hack_chain.assert_called_once()
        self.assertEqual(agent.hack_chain.call_args.kwargs["goals"], ["g"])


class TestDisplayHelpers(unittest.TestCase):
    def test_list_results_count_successes(self):
        with patch(
            "hackagent.interfaces.cli.commands.attack.display.console"
        ) as console:
            _display_attack_results(
                [{"eval_hb": 1, "goal": "a"}, {"eval_jb": 0, "goal": "b"}]
            )
        printed = " ".join(str(call) for call in console.print.call_args_list)
        self.assertIn("Generated 2 result entries", printed)
        self.assertIn("Successful jailbreaks: 1/2", printed)

    def test_empty_list_reports_no_jailbreaks(self):
        with patch(
            "hackagent.interfaces.cli.commands.attack.display.console"
        ) as console:
            _display_attack_results([])
        printed = " ".join(str(call) for call in console.print.call_args_list)
        self.assertIn("Generated 0 result entries", printed)

    def test_dataframe_like_results_render_metrics(self):
        class _FakeFrame:
            columns = ["goal", "prefix", "success_rate"]
            empty = False

            def __len__(self):
                return 3

            def __getitem__(self, key):
                return SimpleNamespace(dtype="float64", mean=lambda: 0.5)

            def head(self):
                return self

        with (
            patch(
                "hackagent.interfaces.cli.commands.attack.display.console"
            ) as console,
            patch(
                "hackagent.interfaces.cli.commands.attack.display.display_results_table"
            ),
        ):
            _display_attack_results(_FakeFrame())
        printed = " ".join(str(call) for call in console.print.call_args_list)
        self.assertIn("Generated 3 result entries", printed)

    def test_summary_mentions_loaded_parameters(self):
        from io import StringIO

        from rich.console import Console

        buffer = StringIO()
        console = Console(file=buffer, width=100, force_terminal=True)
        with patch("hackagent.interfaces.cli.commands.attack.display.console", console):
            _display_attack_summary(
                "bot",
                "litellm",
                "http://x",
                "goal",
                {"attack_type": "tap", "goals": ["g"], "depth": 3},
            )
        self.assertIn("1 parameters loaded", buffer.getvalue())

    def test_generic_info_uses_catalog_label(self):
        from io import StringIO

        from rich.console import Console

        buffer = StringIO()
        console = Console(file=buffer, width=100, force_terminal=True)
        with patch("hackagent.interfaces.cli.commands.attack.display.console", console):
            _display_generic_attack_info("bon")
        self.assertIn("BoN Attack Strategy", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
