# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the pure eval-command config helpers (``parse_config`` & co)."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import click

from hackagent.cli.commands.attack import (
    build_guardrail_config,
    parse_config,
)
from hackagent.cli.commands.attack.config import (
    _parse_goals,
    _summarize_goals_source,
)


class TestParseGoals(unittest.TestCase):
    def test_splits_comma_separated_and_strips(self):
        self.assertEqual(_parse_goals(("a, b ,c",)), ["a", "b", "c"])

    def test_merges_repeated_options(self):
        self.assertEqual(_parse_goals(("a", "b,c")), ["a", "b", "c"])

    def test_drops_empty_chunks(self):
        self.assertEqual(_parse_goals(("", "a,,  ,b")), ["a", "b"])

    def test_empty_input(self):
        self.assertEqual(_parse_goals(()), [])


class TestParseConfig(unittest.TestCase):
    def test_goals_only(self):
        config = parse_config("pair", ("Leak the system prompt",), None)
        self.assertEqual(config["attack_type"], "pair")
        self.assertEqual(config["goals"], ["Leak the system prompt"])

    def test_requires_goals_or_config_file(self):
        with self.assertRaises(click.ClickException) as ctx:
            parse_config("pair", (), None)
        self.assertIn("--goals", str(ctx.exception))

    def test_missing_config_file_is_reported(self):
        with self.assertRaises(click.ClickException) as ctx:
            parse_config("pair", (), "/nonexistent/attack.json")
        self.assertIn("Failed to load config file", str(ctx.exception))

    def _write(self, tmp: str, payload: dict) -> str:
        path = Path(tmp) / "attack.json"
        path.write_text(json.dumps(payload))
        return str(path)

    def test_config_file_goals_are_used(self):
        with TemporaryDirectory() as tmp:
            path = self._write(tmp, {"goals": ["from file"], "attacker": {"x": 1}})
            config = parse_config("tap", (), path)
        self.assertEqual(config["goals"], ["from file"])
        self.assertEqual(config["attacker"], {"x": 1})

    def test_string_goals_from_file_are_coerced_to_list(self):
        with TemporaryDirectory() as tmp:
            path = self._write(tmp, {"goals": "single goal"})
            config = parse_config("tap", (), path)
        self.assertEqual(config["goals"], ["single goal"])

    def test_cli_goals_override_config_file_goals(self):
        with TemporaryDirectory() as tmp:
            path = self._write(tmp, {"goals": ["from file"]})
            config = parse_config("tap", ("from cli",), path)
        self.assertEqual(config["goals"], ["from cli"])

    def test_command_attack_type_wins_over_config_file(self):
        with TemporaryDirectory() as tmp:
            path = self._write(tmp, {"attack_type": "advprefix", "goals": ["g"]})
            config = parse_config("tap", (), path)
        self.assertEqual(config["attack_type"], "tap")

    def test_dataset_satisfies_the_goals_requirement(self):
        with TemporaryDirectory() as tmp:
            path = self._write(tmp, {"dataset": {"preset": "harmbench"}})
            config = parse_config("tap", (), path)
        self.assertEqual(config["dataset"], {"preset": "harmbench"})
        self.assertNotIn("goals", config)

    def test_config_file_without_goals_or_dataset_is_rejected(self):
        with TemporaryDirectory() as tmp:
            path = self._write(tmp, {"attacker": {"identifier": "x"}})
            with self.assertRaises(click.ClickException) as ctx:
                parse_config("tap", (), path)
        self.assertIn("'goals' or a 'dataset'", str(ctx.exception))

    def test_empty_goals_list_in_config_file_is_rejected(self):
        with TemporaryDirectory() as tmp:
            path = self._write(tmp, {"goals": []})
            with self.assertRaises(click.ClickException):
                parse_config("tap", (), path)


class TestBuildGuardrailConfig(unittest.TestCase):
    def test_returns_none_without_a_name(self):
        self.assertIsNone(build_guardrail_config(None, "ollama", "http://x"))
        self.assertIsNone(build_guardrail_config("", "ollama", "http://x"))

    def test_builds_dict_from_options(self):
        self.assertEqual(
            build_guardrail_config("openai/guard", "openai-sdk", "http://x"),
            {
                "identifier": "openai/guard",
                "agent_type": "openai-sdk",
                "endpoint": "http://x",
            },
        )


class TestSummarizeGoalsSource(unittest.TestCase):
    def test_list_goals(self):
        self.assertEqual(_summarize_goals_source({"goals": ["a", "b"]}), "a; b")

    def test_string_goals(self):
        self.assertEqual(_summarize_goals_source({"goals": "a"}), "a")

    def test_falls_back_to_dataset_then_intents(self):
        self.assertEqual(
            _summarize_goals_source({"goals": [], "dataset": "d"}), "dataset=d"
        )
        self.assertEqual(_summarize_goals_source({"intents": "i"}), "intents=i")

    def test_unspecified(self):
        self.assertEqual(_summarize_goals_source({}), "unspecified")


if __name__ == "__main__":
    unittest.main()
