# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest

from hackagent.attacks.techniques.crescendo.config import (
    ATTACKER_SYSTEM_PROMPT,
    DEFAULT_CRESCENDO_CONFIG,
    JUDGE_SYSTEM_PROMPT,
    CrescendoConfig,
)


class TestCrescendoConfig(unittest.TestCase):
    def test_default_has_required_keys(self):
        required = [
            "objective",
            "attacker",
            "judge",
            "max_turns",
            "max_backtracks",
            "jailbreak_threshold",
            "output_dir",
        ]
        for key in required:
            self.assertIn(key, DEFAULT_CRESCENDO_CONFIG)

    def test_default_objective(self):
        self.assertEqual(DEFAULT_CRESCENDO_CONFIG["objective"], "jailbreak")

    def test_default_values(self):
        self.assertEqual(DEFAULT_CRESCENDO_CONFIG["max_turns"], 10)
        self.assertEqual(DEFAULT_CRESCENDO_CONFIG["max_backtracks"], 10)
        self.assertEqual(DEFAULT_CRESCENDO_CONFIG["jailbreak_threshold"], 8)
        self.assertTrue(DEFAULT_CRESCENDO_CONFIG["early_stop_on_success"])
        self.assertEqual(DEFAULT_CRESCENDO_CONFIG["keep_last_n"], 6)

    def test_typed_config_round_trips(self):
        typed = CrescendoConfig.from_dict(
            {
                "max_turns": 5,
                "attacker": {"identifier": "crescendo-attacker"},
            }
        )

        dumped = typed.to_dict()
        self.assertEqual(dumped["attack_type"], "crescendo")
        self.assertEqual(dumped["max_turns"], 5)
        self.assertEqual(dumped["attacker"]["identifier"], "crescendo-attacker")
        self.assertEqual(dumped["objective"], "jailbreak")

    def test_typed_config_accepts_backtrack_and_history_controls(self):
        config = CrescendoConfig.from_dict(
            {
                "keep_last_n": 3,
                "max_backtracks": 2,
                "jailbreak_threshold": 6,
                "early_stop_on_success": False,
            }
        )
        self.assertEqual(config.keep_last_n, 3)
        self.assertEqual(config.max_backtracks, 2)
        self.assertEqual(config.jailbreak_threshold, 6)
        self.assertFalse(config.early_stop_on_success)

    def test_max_turns_must_be_at_least_one(self):
        with self.assertRaises(Exception):
            CrescendoConfig.from_dict({"max_turns": 0})

    def test_jailbreak_threshold_bounds(self):
        with self.assertRaises(Exception):
            CrescendoConfig.from_dict({"jailbreak_threshold": 11})
        with self.assertRaises(Exception):
            CrescendoConfig.from_dict({"jailbreak_threshold": 0})

    def test_prompts_keep_goal_placeholder(self):
        self.assertIn("{goal}", ATTACKER_SYSTEM_PROMPT)
        self.assertIn("{goal}", JUDGE_SYSTEM_PROMPT)

    def test_attacker_prompt_formats_with_goal_only(self):
        formatted = ATTACKER_SYSTEM_PROMPT.format(goal="test goal")
        self.assertIn("test goal", formatted)

    def test_judge_prompt_formats_with_goal_only(self):
        formatted = JUDGE_SYSTEM_PROMPT.format(goal="test goal")
        self.assertIn("test goal", formatted)


if __name__ == "__main__":
    unittest.main()
