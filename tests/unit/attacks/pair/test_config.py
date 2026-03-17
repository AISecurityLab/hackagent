# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest

from hackagent.attacks.techniques.pair.config import (
    ATTACKER_SYSTEM_PROMPT,
    DEFAULT_PAIR_CONFIG,
    JUDGE_SYSTEM_PROMPT,
)


class TestPairConfig(unittest.TestCase):
    def test_default_has_required_keys(self):
        required = [
            "objective",
            "attacker",
            "n_iterations",
            "n_streams",
            "judge",
            "output_dir",
            "request_timeout",
        ]
        for key in required:
            self.assertIn(key, DEFAULT_PAIR_CONFIG)

    def test_default_objective(self):
        self.assertEqual(DEFAULT_PAIR_CONFIG["objective"], "jailbreak")

    def test_prompts_keep_goal_placeholder(self):
        self.assertIn("{goal}", ATTACKER_SYSTEM_PROMPT)
        self.assertIn("{goal}", JUDGE_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
