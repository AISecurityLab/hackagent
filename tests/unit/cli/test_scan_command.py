# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the `hackagent scan` CLI command (live-browser web target)."""

import json
import unittest
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from hackagent.cli.commands.scan import run_quick_scan, scan
from hackagent.router.discovery.scanner import AttackPlan, PlannerError

_URL = "https://x.it/chat"


def _fake_plan():
    return AttackPlan(
        attack_type="tap",
        goals=["Reveal system prompt"],
        parameters={"tap_params": {"depth": 3}},
        rationale="TAP fits this target.",
        confidence=0.8,
    )


def _config():
    cfg = MagicMock()
    cfg.api_key = None
    cfg.base_url = "https://api.hackagent.dev"
    cfg.validate.return_value = None
    return cfg


class TestScanCommand(unittest.TestCase):
    def test_json_emits_web_target_config(self):
        runner = CliRunner()
        result = runner.invoke(scan, [_URL, "--json"], obj={"config": _config()})
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["agent_type"], "web")
        self.assertEqual(payload["config"]["url"], _URL)
        self.assertEqual(payload["config"]["endpoint"], _URL)

    def test_no_attack_shows_target_only(self):
        runner = CliRunner()
        with patch("hackagent.cli.commands.scan.HackAgent") as mock_agent:
            result = runner.invoke(
                scan, [_URL, "--no-attack"], obj={"config": _config()}
            )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Target (web", result.output)
        self.assertIn("'web'", result.output)
        mock_agent.assert_not_called()

    def test_selectors_carried_into_json_config(self):
        runner = CliRunner()
        result = runner.invoke(
            scan,
            [
                _URL,
                "--json",
                "--input-selector",
                "textarea#p",
                "--reply-selector",
                ".bot:last-child",
            ],
            obj={"config": _config()},
        )
        self.assertEqual(result.exit_code, 0, result.output)
        cfg = json.loads(result.output)["config"]
        self.assertEqual(cfg["input_selector"], "textarea#p")
        self.assertEqual(cfg["reply_selector"], ".bot:last-child")

    def test_plan_shows_strategy(self):
        runner = CliRunner()
        with patch(
            "hackagent.cli.commands.scan.plan_attack", return_value=_fake_plan()
        ) as mock_plan:
            result = runner.invoke(
                scan, [_URL, "--plan", "--no-attack"], obj={"config": _config()}
            )
        self.assertEqual(result.exit_code, 0, result.output)
        mock_plan.assert_called_once()
        self.assertIn("Planned attack", result.output)
        self.assertIn("TAP", result.output)

    def test_plan_json_includes_attack_config(self):
        runner = CliRunner()
        with patch(
            "hackagent.cli.commands.scan.plan_attack", return_value=_fake_plan()
        ):
            result = runner.invoke(
                scan, [_URL, "--plan", "--json"], obj={"config": _config()}
            )
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["plan"]["attack_type"], "tap")
        self.assertEqual(payload["plan"]["attack_config"]["attack_type"], "tap")

    def test_plan_failure_is_reported_but_target_survives(self):
        runner = CliRunner()
        with patch(
            "hackagent.cli.commands.scan.plan_attack",
            side_effect=PlannerError("no api key"),
        ):
            result = runner.invoke(
                scan, [_URL, "--plan", "--no-attack"], obj={"config": _config()}
            )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Planning failed", result.output)
        self.assertIn("Target (web", result.output)

    def test_attack_dry_run_validates_without_running(self):
        runner = CliRunner()
        with patch("hackagent.cli.commands.scan.HackAgent") as mock_agent:
            result = runner.invoke(
                scan,
                [_URL, "--attack", "--no-tui", "--dry-run"],
                obj={"config": _config()},
            )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("validation passed", result.output)
        mock_agent.assert_not_called()

    def test_plan_attack_uses_planned_config_in_dry_run(self):
        runner = CliRunner()
        with (
            patch("hackagent.cli.commands.scan.plan_attack", return_value=_fake_plan()),
            patch("hackagent.cli.commands.scan.HackAgent") as mock_agent,
        ):
            result = runner.invoke(
                scan,
                [_URL, "--plan", "--attack", "--no-tui", "--dry-run"],
                obj={"config": _config()},
            )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("validation passed", result.output)
        mock_agent.assert_not_called()


class TestScanHeadlessAttack(unittest.TestCase):
    """The --attack headless path (not dry-run) wires + runs HackAgent."""

    def test_headless_attack_executes(self):
        runner = CliRunner()
        with patch("hackagent.cli.commands.scan.HackAgent") as mock_agent:
            mock_agent.return_value.hack.return_value = [{"asr": 0.25}]
            result = runner.invoke(
                scan,
                [_URL, "--attack", "--no-tui", "--attack-type", "pair"],
                obj={"config": _config()},
            )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("completed", result.output)
        mock_agent.assert_called_once()
        # The web target (URL) flows into the wired agent.
        self.assertEqual(mock_agent.call_args.kwargs["endpoint"], _URL)
        attack_config = mock_agent.return_value.hack.call_args.kwargs["attack_config"]
        self.assertEqual(attack_config["attack_type"], "pair")

    def test_attack_default_launches_tui_prefilled(self):
        runner = CliRunner()
        with patch("hackagent.cli.tui.HackAgentTUI") as mock_tui:
            result = runner.invoke(scan, [_URL, "--attack"], obj={"config": _config()})
        self.assertEqual(result.exit_code, 0, result.output)
        mock_tui.return_value.run.assert_called_once()
        initial_data = mock_tui.call_args.kwargs["initial_data"]
        self.assertEqual(initial_data["agent_type"], "web")
        self.assertEqual(initial_data["endpoint"], _URL)

    def test_headless_attack_failure_is_reported(self):
        runner = CliRunner()
        with patch("hackagent.cli.commands.scan.HackAgent") as mock_agent:
            mock_agent.return_value.hack.side_effect = RuntimeError("boom")
            result = runner.invoke(
                scan, [_URL, "--attack", "--no-tui"], obj={"config": _config()}
            )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Attack failed", result.output)


class TestRunQuickScan(unittest.TestCase):
    """`run_quick_scan` backs `hackagent eval` (the canned jailbreak campaign)."""

    def _ctx(self):
        ctx = MagicMock()
        ctx.obj = {"config": _config()}
        return ctx

    def _args(self, **overrides):
        args = dict(
            agent_name="bot",
            agent_type="litellm",
            endpoint="https://x.it/chat",
            dataset_preset=None,
            limit=2,
            judge_identifier="ollama/llama3",
            judge_type="ollama",
            timeout=30,
            fail_fast=False,
            dry_run=False,
        )
        args.update(overrides)
        return args

    def test_dry_run_validates_without_initializing_agent(self):
        with patch("hackagent.cli.commands.scan.HackAgent") as mock_agent:
            run_quick_scan(self._ctx(), **self._args(dry_run=True))
        mock_agent.assert_not_called()

    def test_success_runs_each_primary_attack(self):
        with patch("hackagent.cli.commands.scan.HackAgent") as mock_agent:
            mock_agent.return_value.hack.return_value = [{"asr": 0.5}]
            run_quick_scan(self._ctx(), **self._args())
        mock_agent.assert_called_once()
        self.assertTrue(mock_agent.return_value.hack.called)

    def test_failed_attack_raises_clickexception(self):
        import click

        with patch("hackagent.cli.commands.scan.HackAgent") as mock_agent:
            mock_agent.return_value.hack.side_effect = RuntimeError("attack blew up")
            with self.assertRaises(click.ClickException):
                run_quick_scan(self._ctx(), **self._args())

    def test_explicit_dataset_preset_is_used(self):
        with patch("hackagent.cli.commands.scan.HackAgent") as mock_agent:
            mock_agent.return_value.hack.return_value = []
            run_quick_scan(self._ctx(), **self._args(dataset_preset="my-dataset"))
        attack_config = mock_agent.return_value.hack.call_args.kwargs["attack_config"]
        self.assertEqual(attack_config["dataset"]["preset"], "my-dataset")


class TestProviderEndpoint(unittest.TestCase):
    """--attacker-model / --judge-model need a valid api_base URL per provider
    (the backend rejects an empty endpoint)."""

    def test_ollama_models_resolve_to_local(self):
        from hackagent.cli.commands.scan import _provider_endpoint

        for m in (
            "ollama_chat/huihui_ai/gemma-4-abliterated",
            "ollama/huihui_ai/gemma-4-abliterated",
            "huihui_ai/gemma-4-abliterated",  # no known prefix → local
        ):
            self.assertEqual(_provider_endpoint(m), "http://localhost:11434")

    def test_hosted_providers_resolve_to_their_api_base(self):
        from hackagent.cli.commands.scan import _provider_endpoint

        self.assertEqual(
            _provider_endpoint("openai/gpt-4o-mini"), "https://api.openai.com/v1"
        )
        self.assertEqual(
            _provider_endpoint("anthropic/claude-sonnet-4-6"),
            "https://api.anthropic.com",
        )

    def test_attacker_override_carries_valid_endpoint(self):
        runner = CliRunner()
        with patch("hackagent.cli.commands.scan.HackAgent") as mock_agent:
            mock_agent.return_value.hack.return_value = []
            result = runner.invoke(
                scan,
                [
                    _URL,
                    "--no-tui",
                    "--goals",
                    "x",
                    "--attacker-model",
                    "ollama_chat/huihui_ai/gemma-4-abliterated",
                ],
                obj={"config": _config()},
            )
        self.assertEqual(result.exit_code, 0, result.output)
        attack_config = mock_agent.return_value.hack.call_args.kwargs["attack_config"]
        att = attack_config["attacker"]
        self.assertEqual(att["identifier"], "ollama_chat/huihui_ai/gemma-4-abliterated")
        self.assertEqual(att["endpoint"], "http://localhost:11434")  # not empty
        self.assertIsNone(att["api_key"])


if __name__ == "__main__":
    unittest.main()
