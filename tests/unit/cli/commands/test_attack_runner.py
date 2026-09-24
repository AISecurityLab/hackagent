# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the shared `hackagent eval <strategy>` execution path."""

import sys
import unittest
from unittest.mock import MagicMock, patch

import click

from hackagent.interfaces.cli.commands.attack import runner as runner_mod
from hackagent.interfaces.cli.commands.attack.runner import _run_attack_command, run_attack


class _Ctx:
    """Click context stand-in whose exit() aborts like the real one."""

    def __init__(self, config):
        self.obj = {"config": config}
        self.exit_calls = []

    def exit(self, code=0):
        self.exit_calls.append(code)
        raise click.exceptions.Exit(code)


def _invoke(ctx, **overrides):
    kwargs = {
        "attack_type": "advprefix",
        "attack_label": "AdvPrefix",
        "agent_name": "target-bot",
        "agent_type": "litellm",
        "endpoint": "http://localhost:8000",
        "goals": ("do something",),
        "config_file": None,
        "timeout": 300,
        "dry_run": False,
        "no_tui": True,
    }
    kwargs.update(overrides)
    return _run_attack_command(ctx, **kwargs)


class TestTuiPath(unittest.TestCase):
    def setUp(self):
        self.config = MagicMock()
        self.ctx = _Ctx(self.config)

    def test_tui_is_launched_with_the_form_prefilled(self):
        app = MagicMock()

        with patch("hackagent.interfaces.tui.HackAgentTUI", return_value=app) as tui_cls:
            _invoke(self.ctx, no_tui=False)

        self.config.validate.assert_called_once_with()
        app.run.assert_called_once_with()
        initial = tui_cls.call_args.kwargs["initial_data"]
        self.assertEqual(initial["agent_name"], "target-bot")
        self.assertEqual(initial["attack_type"], "advprefix")
        self.assertEqual(initial["goals"], "do something")
        self.assertEqual(tui_cls.call_args.kwargs["initial_tab"], "attacks")

    def test_missing_tui_dependency_exits(self):
        with patch.dict(sys.modules, {"hackagent.interfaces.tui": None}):
            with self.assertRaises(click.exceptions.Exit):
                _invoke(self.ctx, no_tui=False)

        self.assertEqual(self.ctx.exit_calls, [1])

    def test_tui_startup_failure_exits(self):
        with patch(
            "hackagent.interfaces.tui.HackAgentTUI", side_effect=RuntimeError("no tty")
        ):
            with self.assertRaises(click.exceptions.Exit):
                _invoke(self.ctx, no_tui=False)

        self.assertEqual(self.ctx.exit_calls, [1])

    def test_invalid_configuration_stops_before_the_tui(self):
        self.config.validate.side_effect = ValueError("API key is required")

        with patch("hackagent.interfaces.tui.HackAgentTUI") as tui_cls:
            with self.assertRaises(ValueError):
                _invoke(self.ctx, no_tui=False)

        tui_cls.assert_not_called()


class TestDirectExecution(unittest.TestCase):
    def setUp(self):
        self.config = MagicMock()
        self.config.api_key = "hk_key"
        self.config.base_url = "https://api.hackagent.dev"
        self.ctx = _Ctx(self.config)
        splash = patch("hackagent.interfaces.cli.banner.display_hackagent_splash")
        splash.start()
        self.addCleanup(splash.stop)

    def test_dry_run_stops_before_creating_an_agent(self):
        with patch.object(runner_mod, "HackAgent") as agent_cls:
            _invoke(self.ctx, dry_run=True)

        agent_cls.assert_not_called()

    def test_successful_run_passes_config_and_timeout(self):
        agent = MagicMock()
        agent.target.return_value = agent
        agent.hack.return_value = [{"goal": "g", "eval_hb": 1}]

        with (
            patch.object(runner_mod, "HackAgent", return_value=agent) as agent_cls,
            patch.object(runner_mod, "_display_attack_results") as display,
        ):
            _invoke(self.ctx, timeout=42)

        self.assertEqual(agent.target.call_args.kwargs["name"], "target-bot")
        self.assertEqual(agent_cls.call_args.args[0].api_key, "hk_key")
        hack_kwargs = agent.hack.call_args.kwargs
        self.assertEqual(hack_kwargs["attack_config"]["attack_type"], "advprefix")
        self.assertEqual(hack_kwargs["attack_config"]["goals"], ["do something"])
        self.assertEqual(hack_kwargs["run_config_override"], {"timeout": 42})
        self.assertTrue(hack_kwargs["fail_on_run_error"])
        display.assert_called_once_with(agent.hack.return_value)

    def test_guardrail_options_are_forwarded(self):
        agent = MagicMock()
        agent.target.return_value = agent

        with (
            patch.object(runner_mod, "HackAgent", return_value=agent) as agent_cls,
            patch.object(runner_mod, "_display_attack_results"),
        ):
            _invoke(
                self.ctx,
                before_guardrail_name="guard-in",
                before_guardrail_type="ollama",
                before_guardrail_endpoint="http://guard",
                after_guardrail_name="guard-out",
            )

        kwargs = agent.target.call_args.kwargs["guardrails"]
        self.assertEqual(
            kwargs["before"],
            {
                "identifier": "guard-in",
                "agent_type": "ollama",
                "endpoint": "http://guard",
            },
        )
        self.assertEqual(kwargs["after"]["identifier"], "guard-out")
        self.assertEqual(agent_cls.call_args.args[0].base_url, "https://api.hackagent.dev")

    def test_no_guardrails_are_passed_as_none(self):
        with (
            patch.object(runner_mod, "HackAgent") as agent_cls,
            patch.object(runner_mod, "_display_attack_results"),
        ):
            _invoke(self.ctx)

        guardrails = agent_cls.return_value.target.call_args.kwargs["guardrails"]
        self.assertIsNone(guardrails["before"])
        self.assertIsNone(guardrails["after"])

    def test_agent_initialisation_failure_is_wrapped(self):
        with patch.object(
            runner_mod, "HackAgent", side_effect=RuntimeError("bad endpoint")
        ):
            with self.assertRaises(click.ClickException) as ctx:
                _invoke(self.ctx)

        self.assertIn("Failed to initialize agent", str(ctx.exception))

    def test_attack_failure_is_wrapped(self):
        agent = MagicMock()
        agent.target.return_value = agent
        agent.hack.side_effect = RuntimeError("target unreachable")

        with patch.object(runner_mod, "HackAgent", return_value=agent):
            with self.assertRaises(click.ClickException) as ctx:
                _invoke(self.ctx)

        self.assertIn("Attack execution failed", str(ctx.exception))

    def test_missing_goals_and_config_file_is_rejected(self):
        with self.assertRaises(click.ClickException):
            _invoke(self.ctx, goals=())

    def test_dataset_configs_are_summarised_for_display(self):
        agent = MagicMock()
        agent.target.return_value = agent

        with (
            patch.object(runner_mod, "HackAgent", return_value=agent),
            patch.object(runner_mod, "_display_attack_results"),
            patch.object(runner_mod, "_display_attack_summary") as summary,
            patch.object(
                runner_mod,
                "_build_attack_config",
                return_value={
                    "attack_type": "advprefix",
                    "dataset": {"preset": "advbench"},
                },
            ),
        ):
            _invoke(self.ctx, goals=())

        self.assertEqual(summary.call_args.args[3], "{'preset': 'advbench'}")

    def test_public_alias_points_at_the_same_implementation(self):
        self.assertIs(run_attack, _run_attack_command)


if __name__ == "__main__":
    unittest.main()
