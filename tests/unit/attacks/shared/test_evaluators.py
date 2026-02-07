# Copyright 2025 - AI4I. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for shared evaluators."""

import unittest

from hackagent.attacks.evaluator import (
    PatternEvaluator,
    KeywordEvaluator,
    LengthEvaluator,
)


class TestPatternEvaluator(unittest.TestCase):
    """Test PatternEvaluator class."""

    def test_success_pattern_match(self):
        """Test that success patterns are detected."""
        evaluator = PatternEvaluator(
            success_patterns=[r"here is the (code|script)", r"def \w+\("],
            failure_patterns=[r"I can't", r"I cannot"],
        )

        self.assertTrue(evaluator.evaluate("Here is the code for your request"))
        self.assertTrue(evaluator.evaluate("Here is the script you asked for"))
        self.assertTrue(evaluator.evaluate("def malware():\n    pass"))

    def test_failure_pattern_blocks_success(self):
        """Test that failure patterns take precedence."""
        evaluator = PatternEvaluator(
            success_patterns=[r"here is"],
            failure_patterns=[r"I can't help", r"I cannot assist"],
        )

        # Even though "here is" might match, failure pattern takes precedence
        response = "I can't help with that. Here is a general explanation."
        self.assertFalse(evaluator.evaluate(response))

    def test_no_pattern_match(self):
        """Test when no patterns match."""
        evaluator = PatternEvaluator(
            success_patterns=[r"success"],
            failure_patterns=[r"failure"],
        )

        self.assertFalse(evaluator.evaluate("This is a neutral response"))

    def test_case_insensitive_by_default(self):
        """Test that matching is case-insensitive by default."""
        evaluator = PatternEvaluator(
            success_patterns=[r"here is the code"],
            failure_patterns=[],
        )

        self.assertTrue(evaluator.evaluate("HERE IS THE CODE"))
        self.assertTrue(evaluator.evaluate("Here Is The Code"))
        self.assertTrue(evaluator.evaluate("here is the code"))

    def test_case_sensitive_mode(self):
        """Test case-sensitive matching."""
        evaluator = PatternEvaluator(
            success_patterns=[r"Here is the code"],
            failure_patterns=[],
            case_sensitive=True,
        )

        self.assertTrue(evaluator.evaluate("Here is the code"))
        self.assertFalse(evaluator.evaluate("here is the code"))

    def test_get_matched_patterns(self):
        """Test get_matched_patterns returns correct matches."""
        evaluator = PatternEvaluator(
            success_patterns=[r"success", r"code"],
            failure_patterns=[r"cannot", r"refuse"],
        )

        response = "I cannot provide that code."
        matches = evaluator.get_matched_patterns(response)

        self.assertIn("code", matches["success_patterns"])
        self.assertIn("cannot", matches["failure_patterns"])

    def test_get_matched_patterns_empty(self):
        """Test get_matched_patterns with no matches."""
        evaluator = PatternEvaluator(
            success_patterns=[r"xyz"],
            failure_patterns=[r"abc"],
        )

        matches = evaluator.get_matched_patterns("No matches here")

        self.assertEqual(matches["success_patterns"], [])
        self.assertEqual(matches["failure_patterns"], [])


class TestKeywordEvaluator(unittest.TestCase):
    """Test KeywordEvaluator class."""

    def test_success_keyword_match(self):
        """Test that success keywords are detected."""
        evaluator = KeywordEvaluator(
            success_keywords=["here is", "as requested"],
            failure_keywords=["cannot", "unable"],
        )

        self.assertTrue(evaluator.evaluate("Here is what you asked for"))
        self.assertTrue(evaluator.evaluate("As requested, here is the code"))

    def test_failure_keyword_blocks_success(self):
        """Test that failure keywords take precedence."""
        evaluator = KeywordEvaluator(
            success_keywords=["here"],
            failure_keywords=["cannot help"],
        )

        response = "I cannot help with that. Here is why."
        self.assertFalse(evaluator.evaluate(response))

    def test_no_keyword_match(self):
        """Test when no keywords match."""
        evaluator = KeywordEvaluator(
            success_keywords=["success"],
            failure_keywords=["failure"],
        )

        self.assertFalse(evaluator.evaluate("A neutral response"))

    def test_case_insensitive_by_default(self):
        """Test that matching is case-insensitive by default."""
        evaluator = KeywordEvaluator(
            success_keywords=["success"],
            failure_keywords=[],
        )

        self.assertTrue(evaluator.evaluate("SUCCESS!"))
        self.assertTrue(evaluator.evaluate("Success achieved"))
        self.assertTrue(evaluator.evaluate("success"))

    def test_case_sensitive_mode(self):
        """Test case-sensitive matching."""
        evaluator = KeywordEvaluator(
            success_keywords=["Success"],
            failure_keywords=[],
            case_sensitive=True,
        )

        self.assertTrue(evaluator.evaluate("Success achieved"))
        self.assertFalse(evaluator.evaluate("success"))
        self.assertFalse(evaluator.evaluate("SUCCESS"))


class TestLengthEvaluator(unittest.TestCase):
    """Test LengthEvaluator class."""

    def test_meets_minimum_length(self):
        """Test response that meets minimum length."""
        evaluator = LengthEvaluator(min_length=10)

        self.assertTrue(evaluator.evaluate("This is a long enough response"))

    def test_below_minimum_length(self):
        """Test response below minimum length."""
        evaluator = LengthEvaluator(min_length=50)

        self.assertFalse(evaluator.evaluate("Too short"))

    def test_whitespace_stripped(self):
        """Test that whitespace is stripped before measuring."""
        evaluator = LengthEvaluator(min_length=10)

        # Actual content is "short" (5 chars) after strip
        self.assertFalse(evaluator.evaluate("    short    "))

    def test_max_length_enforced(self):
        """Test maximum length restriction."""
        evaluator = LengthEvaluator(min_length=5, max_length=20)

        self.assertTrue(evaluator.evaluate("Just right!"))  # 11 chars
        self.assertFalse(
            evaluator.evaluate("This response is way too long for the limit")
        )

    def test_exact_min_length(self):
        """Test response exactly at minimum length."""
        evaluator = LengthEvaluator(min_length=10)

        self.assertTrue(evaluator.evaluate("0123456789"))  # Exactly 10 chars

    def test_exact_max_length(self):
        """Test response exactly at maximum length."""
        evaluator = LengthEvaluator(min_length=5, max_length=10)

        self.assertTrue(evaluator.evaluate("0123456789"))  # Exactly 10 chars

    def test_no_max_length(self):
        """Test evaluator without max_length restriction."""
        evaluator = LengthEvaluator(min_length=5)

        # Very long response should pass
        long_response = "x" * 10000
        self.assertTrue(evaluator.evaluate(long_response))


if __name__ == "__main__":
    unittest.main()
