# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the dashboard attack-builder canvas serializer."""

import unittest

from hackagent.cli.commands.attack.catalog import ATTACK_CATALOG
from hackagent.server.dashboard._builder_config import (
    CanvasValidationError,
    attack_palette,
    build_run_payload,
    canvas_summary,
    new_canvas,
)


def _canvas(**overrides):
    canvas = new_canvas()
    canvas["target"] = {
        "agent_name": "victim",
        "agent_type": "litellm",
        "endpoint": "http://localhost:8000/v1",
    }
    canvas["goals"] = {"mode": "goals", "goals": ["do bad thing"], "dataset": {}}
    canvas["attacks"] = [{"attack_type": "pair", "params": ""}]
    canvas.update(overrides)
    return canvas


class TestAttackPalette(unittest.TestCase):
    def test_palette_covers_full_catalog(self):
        palette = attack_palette()
        self.assertEqual(
            {entry["attack_type"] for entry in palette}, set(ATTACK_CATALOG)
        )
        self.assertTrue(all(entry["label"] for entry in palette))


class TestBuildRunPayload(unittest.TestCase):
    def test_single_attack_builds_hack_config(self):
        payload = build_run_payload(_canvas())
        self.assertEqual(payload["mode"], "single")
        self.assertEqual(
            payload["attack_config"],
            {"attack_type": "pair", "goals": ["do bad thing"]},
        )
        self.assertNotIn("attacks", payload)
        self.assertEqual(payload["target"]["agent_name"], "victim")
        self.assertEqual(payload["timeout"], 300)

    def test_chained_attacks_build_fallback_ladder(self):
        canvas = _canvas(
            attacks=[
                {"attack_type": "pair", "params": ""},
                {"attack_type": "tap", "params": '{"branching_factor": 2}'},
                {"attack_type": "bon", "params": {}},
            ]
        )
        payload = build_run_payload(canvas)
        self.assertEqual(payload["mode"], "chain")
        self.assertEqual(
            [step["attack_type"] for step in payload["attacks"]],
            ["pair", "tap", "bon"],
        )
        # Only the first step carries the goal source, as ``eval chain`` documents.
        self.assertEqual(payload["attacks"][0]["goals"], ["do bad thing"])
        self.assertNotIn("goals", payload["attacks"][1])
        self.assertEqual(payload["attacks"][1]["branching_factor"], 2)
        self.assertEqual(payload["goals"], ["do bad thing"])

    def test_params_cannot_override_block_attack_type(self):
        canvas = _canvas(
            attacks=[{"attack_type": "pair", "params": '{"attack_type": "tap"}'}]
        )
        self.assertEqual(
            build_run_payload(canvas)["attack_config"]["attack_type"], "pair"
        )

    def test_dataset_mode_builds_dataset_section(self):
        canvas = _canvas(
            goals={
                "mode": "dataset",
                "goals": [],
                "dataset": {"preset": "advbench", "limit": "25", "split": ""},
            }
        )
        payload = build_run_payload(canvas)
        self.assertEqual(
            payload["attack_config"]["dataset"], {"preset": "advbench", "limit": 25}
        )
        self.assertNotIn("goals", payload["attack_config"])

    def test_guardrails_mirror_cli_shape(self):
        canvas = _canvas(
            guardrails={
                "before": {
                    "identifier": "openai/guard",
                    "agent_type": "openai-sdk",
                    "endpoint": "http://guard/v1",
                },
                "after": {"identifier": "", "agent_type": "", "endpoint": ""},
            }
        )
        payload = build_run_payload(canvas)
        self.assertEqual(
            payload["before_guardrail"],
            {
                "identifier": "openai/guard",
                "agent_type": "openai-sdk",
                "endpoint": "http://guard/v1",
            },
        )
        self.assertIsNone(payload["after_guardrail"])


class TestCanvasValidation(unittest.TestCase):
    def test_missing_target_fields(self):
        for field in ("agent_name", "endpoint"):
            canvas = _canvas()
            canvas["target"][field] = ""
            with self.assertRaises(CanvasValidationError):
                build_run_payload(canvas)

    def test_no_attack_blocks(self):
        with self.assertRaises(CanvasValidationError):
            build_run_payload(_canvas(attacks=[]))

    def test_unknown_attack_type(self):
        with self.assertRaises(CanvasValidationError):
            build_run_payload(_canvas(attacks=[{"attack_type": "nope"}]))

    def test_no_goals_and_no_dataset(self):
        canvas = _canvas(goals={"mode": "goals", "goals": ["  "], "dataset": {}})
        with self.assertRaises(CanvasValidationError):
            build_run_payload(canvas)

    def test_incomplete_dataset_block(self):
        canvas = _canvas(
            goals={"mode": "dataset", "goals": [], "dataset": {"provider": "file"}}
        )
        with self.assertRaises(CanvasValidationError):
            build_run_payload(canvas)

    def test_invalid_params_json(self):
        canvas = _canvas(attacks=[{"attack_type": "pair", "params": "{oops"}])
        with self.assertRaises(CanvasValidationError):
            build_run_payload(canvas)

    def test_invalid_timeout(self):
        with self.assertRaises(CanvasValidationError):
            build_run_payload(_canvas(timeout="soon"))


class TestCanvasSummary(unittest.TestCase):
    def test_summary_uses_catalog_labels(self):
        canvas = _canvas(
            attacks=[{"attack_type": "pair"}, {"attack_type": "tap"}],
        )
        self.assertEqual(canvas_summary(canvas), "victim · PAIR → TAP")

    def test_summary_of_empty_canvas(self):
        self.assertEqual(canvas_summary(new_canvas()), "no target · no attacks")


if __name__ == "__main__":
    unittest.main()
