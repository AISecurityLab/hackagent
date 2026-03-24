# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest

from hackagent.attacks.techniques.tap.generation import (
    _resolve_on_topic_judges_config,
)


class TestResolveOnTopicJudgesConfig(unittest.TestCase):
    def test_uses_explicit_on_topic_judge(self):
        cfg = _resolve_on_topic_judges_config(
            on_topic={"identifier": "my-on-topic", "endpoint": "http://judge"},
            fallback_judges=[{"identifier": "fallback", "endpoint": "http://fb"}],
        )

        self.assertIsNotNone(cfg)
        self.assertEqual(len(cfg), 1)
        self.assertEqual(cfg[0]["identifier"], "my-on-topic")
        self.assertEqual(cfg[0]["type"], "on_topic")

    def test_fallbacks_to_standard_judge_when_missing(self):
        cfg = _resolve_on_topic_judges_config(
            on_topic=None,
            fallback_judges=[
                {
                    "identifier": "standard-judge",
                    "endpoint": "http://judge",
                    "agent_type": "OPENAI_SDK",
                    "type": "harmbench",
                }
            ],
        )

        self.assertIsNotNone(cfg)
        self.assertEqual(len(cfg), 1)
        self.assertEqual(cfg[0]["identifier"], "standard-judge")
        self.assertEqual(cfg[0]["endpoint"], "http://judge")
        # Force on-topic evaluator semantics even when reusing judge backend.
        self.assertEqual(cfg[0]["type"], "on_topic")

    def test_no_on_topic_and_no_judge_returns_none(self):
        cfg = _resolve_on_topic_judges_config(on_topic=None, fallback_judges=None)
        self.assertIsNone(cfg)


if __name__ == "__main__":
    unittest.main()
