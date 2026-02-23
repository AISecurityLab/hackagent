# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for hackagent.attacks.evaluator.judge_evaluators module."""

import unittest
from unittest.mock import MagicMock, patch

from hackagent.attacks.evaluator.judge_evaluators import (
    EVALUATOR_MAP,
    HarmBenchEvaluator,
    JailbreakBenchEvaluator,
    NuancedEvaluator,
)


class TestEvaluatorMap(unittest.TestCase):
    """Test the EVALUATOR_MAP registry."""

    def test_evaluator_map_has_all_evaluators(self):
        """Test that EVALUATOR_MAP contains all evaluators."""
        self.assertIn("nuanced", EVALUATOR_MAP)
        self.assertIn("jailbreakbench", EVALUATOR_MAP)
        self.assertIn("harmbench", EVALUATOR_MAP)

    def test_evaluator_map_values_are_classes(self):
        """Test that EVALUATOR_MAP values are classes."""
        self.assertIs(EVALUATOR_MAP["nuanced"], NuancedEvaluator)
        self.assertIs(EVALUATOR_MAP["jailbreakbench"], JailbreakBenchEvaluator)
        self.assertIs(EVALUATOR_MAP["harmbench"], HarmBenchEvaluator)


class TestNuancedEvaluatorClassAttributes(unittest.TestCase):
    """Test NuancedEvaluator class attributes."""

    def test_eval_column(self):
        self.assertEqual(NuancedEvaluator.eval_column, "eval_nj")

    def test_explanation_column(self):
        self.assertEqual(NuancedEvaluator.explanation_column, "explanation_nj")

    def test_has_prompt(self):
        self.assertIn("classifier", NuancedEvaluator.PROMPT)
        self.assertIn("{request}", NuancedEvaluator.PROMPT)
        self.assertIn("{response}", NuancedEvaluator.PROMPT)


class TestNuancedEvaluatorParsing(unittest.TestCase):
    """Test NuancedEvaluator._parse_response_content and _check_assertion."""

    @patch("hackagent.attacks.evaluator.base.create_router")
    def setUp(self, mock_create_router):
        """Set up NuancedEvaluator."""
        mock_create_router.return_value = (MagicMock(), "test-key")
        mock_client = MagicMock()
        mock_client.token = "test-token"
        mock_config = MagicMock()
        mock_config.model_id = "test-model"
        mock_config.agent_endpoint = "http://localhost"
        mock_config.agent_type = MagicMock()
        mock_config.agent_type.value = "litellm"
        mock_config.max_new_tokens_eval = 100
        mock_config.temperature = 0.0
        mock_config.request_timeout = 30
        mock_config.agent_metadata = {}
        mock_config.agent_name = "nuanced-judge"
        self.evaluator = NuancedEvaluator(client=mock_client, config=mock_config)

    def test_parse_violating(self):
        """Test parsing 1_violating response."""
        score, expl = self.evaluator._parse_response_content(
            "The response is clearly harmful. 1_violating", 0
        )
        self.assertEqual(score, 1)
        self.assertIn("Violating", expl)

    def test_parse_compliant(self):
        """Test parsing 0_compliant response."""
        score, expl = self.evaluator._parse_response_content(
            "The response refuses the request. 0_compliant", 0
        )
        self.assertEqual(score, 0)
        self.assertIn("Compliant", expl)

    def test_parse_unknown_label(self):
        """Test parsing response with no recognized label."""
        score, expl = self.evaluator._parse_response_content(
            "I'm not sure about this one.", 0
        )
        self.assertEqual(score, 0)
        self.assertIn("Unknown label", expl)

    def test_parse_none_content(self):
        """Test parsing None content."""
        score, expl = self.evaluator._parse_response_content(None, 0)
        self.assertEqual(score, 0)
        self.assertIn("No content", expl)

    def test_check_assertion_violating_confident(self):
        """Test _check_assertion with violating content is confident."""
        result = self.evaluator._check_assertion("1_violating", 0)
        self.assertTrue(result.is_confident)
        self.assertEqual(result.score, 1)

    def test_check_assertion_compliant_confident(self):
        """Test _check_assertion with compliant content is confident."""
        result = self.evaluator._check_assertion("0_compliant", 0)
        self.assertTrue(result.is_confident)
        self.assertEqual(result.score, 0)

    def test_check_assertion_unknown_not_confident(self):
        """Test _check_assertion with unknown content is not confident."""
        result = self.evaluator._check_assertion("ambiguous response", 0)
        self.assertFalse(result.is_confident)

    def test_check_assertion_none_not_confident(self):
        """Test _check_assertion with None content is not confident."""
        result = self.evaluator._check_assertion(None, 0)
        self.assertFalse(result.is_confident)

    def test_get_request_data_for_row(self):
        """Test _get_request_data_for_row formats prompt correctly."""
        row = {"goal": "test goal", "completion": "test completion"}
        data = self.evaluator._get_request_data_for_row(row)
        self.assertIn("messages", data)
        content = data["messages"][0]["content"]
        self.assertIn("test goal", content)
        self.assertIn("test completion", content)


class TestJailbreakBenchEvaluatorClassAttributes(unittest.TestCase):
    """Test JailbreakBenchEvaluator class attributes."""

    def test_eval_column(self):
        self.assertEqual(JailbreakBenchEvaluator.eval_column, "eval_jb")

    def test_explanation_column(self):
        self.assertEqual(JailbreakBenchEvaluator.explanation_column, "explanation_jb")

    def test_has_prompt(self):
        self.assertIn("classifier", JailbreakBenchEvaluator.PROMPT)
        self.assertIn("{generation}", JailbreakBenchEvaluator.PROMPT)


class TestJailbreakBenchEvaluatorParsing(unittest.TestCase):
    """Test JailbreakBenchEvaluator._parse_response_content."""

    @patch("hackagent.attacks.evaluator.base.create_router")
    def setUp(self, mock_create_router):
        """Set up JailbreakBenchEvaluator."""
        mock_create_router.return_value = (MagicMock(), "test-key")
        mock_client = MagicMock()
        mock_client.token = "test-token"
        mock_config = MagicMock()
        mock_config.model_id = "test-model"
        mock_config.agent_endpoint = "http://localhost"
        mock_config.agent_type = MagicMock()
        mock_config.agent_type.value = "litellm"
        mock_config.max_new_tokens_eval = 100
        mock_config.temperature = 0.0
        mock_config.request_timeout = 30
        mock_config.agent_metadata = {}
        mock_config.agent_name = "jailbreak-judge"
        self.evaluator = JailbreakBenchEvaluator(client=mock_client, config=mock_config)

    def test_parse_yes(self):
        """Test parsing 'yes' response."""
        score, expl = self.evaluator._parse_response_content("yes", 0)
        self.assertEqual(score, 1)
        self.assertIn("Jailbreak", expl)

    def test_parse_no(self):
        """Test parsing 'no' response."""
        score, expl = self.evaluator._parse_response_content("no", 0)
        self.assertEqual(score, 0)
        self.assertIn("jailbreak", expl.lower())

    def test_get_request_data_for_row(self):
        """Test _get_request_data_for_row formats prompt correctly."""
        row = {"completion": "test output"}
        data = self.evaluator._get_request_data_for_row(row)
        content = data["messages"][0]["content"]
        self.assertIn("test output", content)


class TestHarmBenchEvaluatorClassAttributes(unittest.TestCase):
    """Test HarmBenchEvaluator class attributes."""

    def test_eval_column(self):
        self.assertEqual(HarmBenchEvaluator.eval_column, "eval_hb")

    def test_explanation_column(self):
        self.assertEqual(HarmBenchEvaluator.explanation_column, "explanation_hb")

    def test_has_prompt(self):
        self.assertIn("{behavior}", HarmBenchEvaluator.PROMPT)
        self.assertIn("{generation}", HarmBenchEvaluator.PROMPT)


class TestHarmBenchEvaluatorParsing(unittest.TestCase):
    """Test HarmBenchEvaluator._parse_response_content."""

    @patch("hackagent.attacks.evaluator.base.create_router")
    def setUp(self, mock_create_router):
        """Set up HarmBenchEvaluator."""
        mock_create_router.return_value = (MagicMock(), "test-key")
        mock_client = MagicMock()
        mock_client.token = "test-token"
        mock_config = MagicMock()
        mock_config.model_id = "test-model"
        mock_config.agent_endpoint = "http://localhost"
        mock_config.agent_type = MagicMock()
        mock_config.agent_type.value = "litellm"
        mock_config.max_new_tokens_eval = 100
        mock_config.temperature = 0.0
        mock_config.request_timeout = 30
        mock_config.agent_metadata = {}
        mock_config.agent_name = "harmbench-judge"
        self.evaluator = HarmBenchEvaluator(client=mock_client, config=mock_config)

    def test_parse_yes(self):
        """Test parsing 'yes' response."""
        score, expl = self.evaluator._parse_response_content("yes", 0)
        self.assertEqual(score, 1)

    def test_parse_no(self):
        """Test parsing 'no' response."""
        score, expl = self.evaluator._parse_response_content("no", 0)
        self.assertEqual(score, 0)

    def test_get_request_data_for_row(self):
        """Test _get_request_data_for_row formats prompt correctly."""
        row = {"goal": "harmful behavior", "completion": "harmful response"}
        data = self.evaluator._get_request_data_for_row(row)
        content = data["messages"][0]["content"]
        self.assertIn("harmful behavior", content)
        self.assertIn("harmful response", content)


if __name__ == "__main__":
    unittest.main()
