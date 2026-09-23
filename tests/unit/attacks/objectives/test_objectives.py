# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for attack objective configs and the objective registry."""

import unittest

from hackagent.evaluation.patterns import PatternEvaluator
from hackagent.attacks.objectives import (
    HARMFUL_BEHAVIOR,
    JAILBREAK,
    OBJECTIVES,
    POLICY_VIOLATION,
    ObjectiveConfig,
)
from hackagent.attacks.objectives.rag import RAG


class TestObjectiveConfig(unittest.TestCase):
    def test_to_dict_round_trips_fields(self):
        objective = ObjectiveConfig(
            name="custom",
            success_patterns=[r"ok"],
            failure_patterns=[r"nope"],
            evaluation_criteria="judge this",
            description="desc",
        )
        self.assertEqual(
            objective.to_dict(),
            {
                "name": "custom",
                "success_patterns": [r"ok"],
                "failure_patterns": [r"nope"],
                "evaluation_criteria": "judge this",
                "description": "desc",
            },
        )

    def test_description_defaults_empty(self):
        objective = ObjectiveConfig(
            name="x",
            success_patterns=[],
            failure_patterns=[],
            evaluation_criteria="",
        )
        self.assertEqual(objective.description, "")


class TestObjectiveRegistry(unittest.TestCase):
    def test_known_objectives_are_registered(self):
        self.assertEqual(
            set(OBJECTIVES),
            {"jailbreak", "harmful_behavior", "policy_violation", "rag"},
        )
        self.assertIs(OBJECTIVES["jailbreak"], JAILBREAK)
        self.assertIs(OBJECTIVES["harmful_behavior"], HARMFUL_BEHAVIOR)
        self.assertIs(OBJECTIVES["policy_violation"], POLICY_VIOLATION)
        self.assertIs(OBJECTIVES["rag"], RAG)

    def test_each_registered_objective_has_patterns_and_criteria(self):
        for name, objective in OBJECTIVES.items():
            self.assertEqual(objective.name, name)
            self.assertTrue(objective.success_patterns)
            self.assertTrue(objective.failure_patterns)
            self.assertTrue(objective.evaluation_criteria.strip())
            self.assertTrue(objective.description)


class TestObjectivePatternSemantics(unittest.TestCase):
    def _evaluator(self, objective: ObjectiveConfig) -> PatternEvaluator:
        return PatternEvaluator(
            success_patterns=objective.success_patterns,
            failure_patterns=objective.failure_patterns,
        )

    def test_jailbreak_detects_refusal_as_failure(self):
        evaluator = self._evaluator(JAILBREAK)
        self.assertFalse(evaluator.evaluate("I'm sorry, I cannot help with that."))
        self.assertTrue(
            evaluator.evaluate("Here's how you can proceed. First, gather tools.")
        )

    def test_harmful_behavior_requires_actionable_content(self):
        evaluator = self._evaluator(HARMFUL_BEHAVIOR)
        self.assertFalse(evaluator.evaluate("As an AI I am unable to assist."))
        self.assertTrue(
            evaluator.evaluate(
                "Here is a step-by-step procedure and the script to run."
            )
        )

    def test_policy_violation_failure_patterns_take_precedence(self):
        evaluator = self._evaluator(POLICY_VIOLATION)
        self.assertFalse(
            evaluator.evaluate(
                "I cannot provide detailed instructions. As an AI it violates my guidelines."
            )
        )
        self.assertTrue(
            evaluator.evaluate("Here is a detailed, specific, step-by-step example.")
        )

    def test_rag_success_mentions_retrieved_context(self):
        evaluator = self._evaluator(RAG)
        self.assertTrue(
            evaluator.evaluate("According to the documents, reset the password now.")
        )
        self.assertFalse(evaluator.evaluate("I'm sorry, I can't assist with that."))


if __name__ == "__main__":
    unittest.main()
