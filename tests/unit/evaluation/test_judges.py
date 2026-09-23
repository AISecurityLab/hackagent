# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest

from hackagent.core.contracts import Sample
from hackagent.evaluation.judges import (
    EVALUATOR_MAP,
    NuancedJudge,
    RagOutcomeJudge,
    ScorerJudge,
    parse_yes_no,
)


class TestParseYesNo(unittest.TestCase):
    def test_yes_and_no(self):
        yes = parse_yes_no("yes")
        no = parse_yes_no("No")
        self.assertEqual(yes.score, 1)
        self.assertTrue(yes.is_confident)
        self.assertEqual(no.score, 0)
        self.assertTrue(no.is_confident)

    def test_empty_is_not_confident(self):
        parsed = parse_yes_no("   ")
        self.assertEqual(parsed.score, 0)
        self.assertFalse(parsed.is_confident)


class TestJudgeParsers(unittest.TestCase):
    def test_nuanced_violating_label(self):
        parsed = NuancedJudge().parse("The reply is detailed. 1_violating")
        self.assertEqual(parsed.score, 1)
        self.assertTrue(parsed.is_confident)

    def test_scorer_bracket_rating(self):
        parsed = ScorerJudge().parse("Rating: [[7]]")
        self.assertEqual(parsed.score, 7)
        self.assertTrue(parsed.is_confident)

    def test_rag_outcome_json(self):
        parsed = RagOutcomeJudge().parse(
            '{"classification": "SUCCESS", "rationale": "followed the poison"}'
        )
        self.assertEqual(parsed.score, 1)
        self.assertTrue(parsed.is_confident)
        self.assertIn("SUCCESS", parsed.explanation)

    def test_rag_outcome_is_registered(self):
        self.assertIn("rag_outcome", EVALUATOR_MAP)
        self.assertIs(EVALUATOR_MAP["rag_outcome"], RagOutcomeJudge)

    def test_rag_render_uses_sample_fields(self):
        prompt = RagOutcomeJudge().render(
            Sample(goal="exfiltrate", prompt="what is the policy?", response="here")
        )
        self.assertIn("exfiltrate", prompt)
        self.assertIn("what is the policy?", prompt)
        self.assertIn("here", prompt)


if __name__ == "__main__":
    unittest.main()
