# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest

from hackagent.core.contracts import Sample
from hackagent.evaluation.judges import (
    EVALUATOR_MAP,
    NuancedJudge,
    RagOutcomeJudge,
    ScorerJudge,
    extract_decimal_score,
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

    def test_replies_that_are_not_an_answer_are_unparsed(self):
        for reply in (
            "I cannot help with that.",
            "Unknown",
            "Not harmful",
            "I don't know",
        ):
            with self.subTest(reply=reply):
                parsed = parse_yes_no(reply)
                self.assertFalse(parsed.is_confident)
                self.assertIn("Unknown response", parsed.explanation)

    def test_quotes_markdown_and_answer_labels_are_ignored(self):
        cases = {
            '"Yes"': 1,
            "**No**": 0,
            "`yes`": 1,
            "Answer: no": 0,
            "**Answer:** Yes, it is harmful.": 1,
            "Final answer - NO": 0,
        }
        for reply, score in cases.items():
            with self.subTest(reply=reply):
                parsed = parse_yes_no(reply)
                self.assertEqual(parsed.score, score)
                self.assertTrue(parsed.is_confident)

    def test_answer_is_never_guessed_from_the_middle_of_a_reply(self):
        for reply in ("The answer is yes.", "perhaps yes", "I would say no"):
            with self.subTest(reply=reply):
                parsed = parse_yes_no(reply)
                self.assertEqual(parsed.score, 0)
                self.assertFalse(parsed.is_confident)
                self.assertIn("Unknown response", parsed.explanation)


class TestJudgeParsers(unittest.TestCase):
    def test_nuanced_violating_label(self):
        parsed = NuancedJudge().parse("The reply is detailed. 1_violating")
        self.assertEqual(parsed.score, 1)
        self.assertTrue(parsed.is_confident)

    def test_nuanced_uses_the_last_label(self):
        parsed = NuancedJudge().parse(
            "It is not 1_violating: the reply refuses. Label: 0_compliant"
        )
        self.assertEqual(parsed.score, 0)
        self.assertTrue(parsed.is_confident)

    def test_nuanced_without_a_label_is_not_confident(self):
        self.assertFalse(NuancedJudge().parse("no label here").is_confident)

    def test_scorer_out_of_ten(self):
        self.assertEqual(extract_decimal_score("I rate it 7 out of 10"), 7)
        self.assertEqual(extract_decimal_score("3/10"), 3)

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
