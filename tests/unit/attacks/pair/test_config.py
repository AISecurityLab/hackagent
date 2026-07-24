# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest

from hackagent.attacks.techniques.pair.config import (
    ATTACKER_SYSTEM_PROMPT,
    DEFAULT_PAIR_CONFIG,
    JUDGE_SYSTEM_PROMPT,
    PairConfig,
)


class TestPairConfig(unittest.TestCase):
    def test_default_has_required_keys(self):
        required = [
            "objective",
            "attacker",
            "category_classifier",
            "n_iterations",
            "n_streams",
            "judge",
            "output_dir",
        ]
        for key in required:
            self.assertIn(key, DEFAULT_PAIR_CONFIG)

    def test_default_objective(self):
        self.assertEqual(DEFAULT_PAIR_CONFIG["objective"], "jailbreak")

    def test_typed_config_round_trips(self):
        typed = PairConfig.from_dict(
            {
                "n_iterations": 3,
                "attacker": {"identifier": "pair-attacker"},
            }
        )

        dumped = typed.to_dict()
        self.assertEqual(dumped["attack_type"], "pair")
        self.assertEqual(dumped["n_iterations"], 3)
        self.assertEqual(dumped["attacker"]["identifier"], "pair-attacker")
        self.assertEqual(dumped["objective"], "jailbreak")

    def test_typed_config_accepts_pair_history_controls(self):
        config = PairConfig.from_dict(
            {
                "keep_last_n": 2,
                "target_str": "Sure, here is the requested answer",
                "translate_prompts": False,
            }
        )
        self.assertEqual(config.keep_last_n, 2)
        self.assertEqual(config.target_str, "Sure, here is the requested answer")
        self.assertFalse(config.translate_prompts)

    def test_prompts_keep_goal_placeholder(self):
        self.assertIn("{goal}", ATTACKER_SYSTEM_PROMPT)
        self.assertIn("{target_str}", ATTACKER_SYSTEM_PROMPT)
        self.assertIn("{goal}", JUDGE_SYSTEM_PROMPT)

    def test_attacker_prompt_has_no_language_directive_placeholder(self):
        # Language is handled by translating the whole prompt (see
        # the translation module), not by an in-prompt directive.
        self.assertNotIn("{language_directive}", ATTACKER_SYSTEM_PROMPT)
        # Formats with only the goal placeholder.
        self.assertIn(
            "Sure, here is",
            ATTACKER_SYSTEM_PROMPT.format(goal="x", target_str="Sure, here is"),
        )


if __name__ == "__main__":
    unittest.main()
