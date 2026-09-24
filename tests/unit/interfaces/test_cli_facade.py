# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""CLI commands that must talk to the facade, not a second implementation."""

import unittest
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from hackagent.interfaces.cli.commands.scan import run_quick_scan
from hackagent.interfaces.cli.main import cli


def _config():
    cfg = MagicMock()
    cfg.api_key = None
    cfg.base_url = "https://api.hackagent.dev"
    cfg.validate.return_value = None
    return cfg


class TestStrategyRegistry(unittest.TestCase):
    def test_eval_help_lists_crescendo_and_rag(self):
        result = CliRunner().invoke(cli, ["eval", "--help"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("crescendo", result.output)
        self.assertIn("rag", result.output)


class TestQuickScanUsesHackChain(unittest.TestCase):
    def test_quick_scan_runs_the_campaign_through_facade_hack_chain(self):
        ctx = MagicMock()
        ctx.obj = {"config": _config()}
        with patch(
            "hackagent.interfaces.cli.commands.scan.quick.HackAgent"
        ) as session_cls:
            bound = session_cls.return_value.target.return_value
            bound.hack_chain.return_value = [
                {"asr": 0.5, "chain_attack_type": "h4rm3l"}
            ]
            bound.hack.return_value = [{"should": "not run"}]
            run_quick_scan(
                ctx,
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

        session_cls.return_value.target.assert_called_once()
        self.assertEqual(
            session_cls.return_value.target.call_args.args[0], "https://x.it/chat"
        )
        bound.hack_chain.assert_called_once()
        bound.hack.assert_not_called()
        attacks = bound.hack_chain.call_args.kwargs["attacks"]
        self.assertGreaterEqual(len(attacks), 1)
        self.assertEqual(attacks[0]["dataset"]["limit"], 2)
        self.assertIn("attack_type", attacks[0])
