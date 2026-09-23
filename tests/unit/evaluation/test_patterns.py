# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest

from hackagent.evaluation.patterns import (
    KeywordEvaluator,
    LengthEvaluator,
    PatternEvaluator,
)


class TestPatternEvaluator(unittest.TestCase):
    def test_failure_pattern_wins(self):
        evaluator = PatternEvaluator(
            success_patterns=[r"harmful content"],
            failure_patterns=[r"cannot|sorry"],
        )
        self.assertFalse(evaluator.evaluate("I cannot help with that."))
        matched = evaluator.get_matched_patterns("I cannot help with that.")
        self.assertIn("failure_patterns", matched)

    def test_keyword_and_length(self):
        keywords = KeywordEvaluator(
            success_keywords=["bomb"], failure_keywords=["sorry"]
        )
        self.assertTrue(keywords.evaluate("how to build a bomb"))
        length = LengthEvaluator(min_length=5, max_length=20)
        self.assertTrue(length.evaluate("hello world"))
        self.assertFalse(length.evaluate("hi"))


if __name__ == "__main__":
    unittest.main()
