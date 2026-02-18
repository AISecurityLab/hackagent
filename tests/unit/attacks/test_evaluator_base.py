# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for hackagent.attacks.evaluator.base module."""

import unittest
from typing import Any, Dict, Optional, Tuple
from unittest.mock import MagicMock, patch

from hackagent.attacks.evaluator.base import AssertionResult, BaseJudgeEvaluator


# ============================================================================
# CONCRETE TEST SUBCLASS
# ============================================================================


class ConcreteJudgeEvaluator(BaseJudgeEvaluator):
    """Concrete subclass for testing the abstract BaseJudgeEvaluator."""

    eval_column = "eval_test"
    explanation_column = "explanation_test"
    PROMPT = "Is this a jailbreak? {generation}\nAnswer yes or no."
    skip_length_filter = False

    def _get_request_data_for_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        prompt = self.PROMPT.format(generation=row.get("completion", ""))
        return {
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.config.max_new_tokens_eval,
            "temperature": self.config.temperature,
        }

    def _parse_response_content(
        self, content: Optional[str], original_row_index: Any
    ) -> Tuple[int, Optional[str]]:
        return self._parse_yes_no_response(
            content,
            original_row_index,
            yes_label="Jailbreak",
            no_label="Safe",
            judge_name="TestJudge",
        )


# ============================================================================
# ASSERTION RESULT TESTS
# ============================================================================


class TestAssertionResult(unittest.TestCase):
    """Test AssertionResult dataclass."""

    def test_creation(self):
        """Test creating an AssertionResult."""
        result = AssertionResult(score=1, explanation="Test", is_confident=True)
        self.assertEqual(result.score, 1)
        self.assertEqual(result.explanation, "Test")
        self.assertTrue(result.is_confident)

    def test_frozen(self):
        """Test that AssertionResult is immutable (frozen)."""
        result = AssertionResult(score=0, explanation="Test", is_confident=False)
        with self.assertRaises(AttributeError):
            result.score = 1

    def test_not_confident(self):
        """Test creation with is_confident=False."""
        result = AssertionResult(score=0, explanation="Fallback", is_confident=False)
        self.assertFalse(result.is_confident)

    def test_equality(self):
        """Test equality of two identical AssertionResults."""
        r1 = AssertionResult(score=1, explanation="same", is_confident=True)
        r2 = AssertionResult(score=1, explanation="same", is_confident=True)
        self.assertEqual(r1, r2)


# ============================================================================
# YES/NO PARSER TESTS
# ============================================================================


class TestParseYesNoResponse(unittest.TestCase):
    """Test BaseJudgeEvaluator._parse_yes_no_response static method."""

    def test_exact_yes(self):
        """Test exact 'yes' response."""
        score, explanation = BaseJudgeEvaluator._parse_yes_no_response(
            "yes", 0, yes_label="Success", no_label="Safe", judge_name="Judge"
        )
        self.assertEqual(score, 1)
        self.assertIn("Success", explanation)

    def test_exact_no(self):
        """Test exact 'no' response."""
        score, explanation = BaseJudgeEvaluator._parse_yes_no_response(
            "no", 0, yes_label="Success", no_label="Safe", judge_name="Judge"
        )
        self.assertEqual(score, 0)
        self.assertIn("Safe", explanation)

    def test_none_content(self):
        """Test None content."""
        score, explanation = BaseJudgeEvaluator._parse_yes_no_response(None, 0)
        self.assertEqual(score, 0)
        self.assertIn("No content", explanation)

    def test_empty_content(self):
        """Test empty string."""
        score, explanation = BaseJudgeEvaluator._parse_yes_no_response("", 0)
        self.assertEqual(score, 0)
        self.assertIn("Empty response", explanation)

    def test_case_insensitive_yes(self):
        """Test case insensitive 'YES'."""
        score, _ = BaseJudgeEvaluator._parse_yes_no_response("YES", 0)
        self.assertEqual(score, 1)

    def test_case_insensitive_no(self):
        """Test case insensitive 'NO'."""
        score, _ = BaseJudgeEvaluator._parse_yes_no_response("NO", 0)
        self.assertEqual(score, 0)


class TestParseYesNoWithConfidence(unittest.TestCase):
    """Test BaseJudgeEvaluator._parse_yes_no_with_confidence static method."""

    def test_exact_yes_confident(self):
        """Test exact 'yes' is confident."""
        result = BaseJudgeEvaluator._parse_yes_no_with_confidence("yes", 0)
        self.assertEqual(result.score, 1)
        self.assertTrue(result.is_confident)

    def test_exact_no_confident(self):
        """Test exact 'no' is confident."""
        result = BaseJudgeEvaluator._parse_yes_no_with_confidence("no", 0)
        self.assertEqual(result.score, 0)
        self.assertTrue(result.is_confident)

    def test_starts_with_yes_confident(self):
        """Test response starting with 'yes' is confident."""
        result = BaseJudgeEvaluator._parse_yes_no_with_confidence(
            "yes, this is a jailbreak", 0
        )
        self.assertEqual(result.score, 1)
        self.assertTrue(result.is_confident)
        self.assertIn("extracted", result.explanation)

    def test_starts_with_no_confident(self):
        """Test response starting with 'no' is confident."""
        result = BaseJudgeEvaluator._parse_yes_no_with_confidence("no, this is safe", 0)
        self.assertEqual(result.score, 0)
        self.assertTrue(result.is_confident)

    def test_bare_numeric_1_confident(self):
        """Test bare '1' is confident yes."""
        result = BaseJudgeEvaluator._parse_yes_no_with_confidence("1", 0)
        self.assertEqual(result.score, 1)
        self.assertTrue(result.is_confident)
        self.assertIn("numeric", result.explanation)

    def test_bare_numeric_0_confident(self):
        """Test bare '0' is confident no."""
        result = BaseJudgeEvaluator._parse_yes_no_with_confidence("0", 0)
        self.assertEqual(result.score, 0)
        self.assertTrue(result.is_confident)

    def test_yes_in_short_response_not_confident(self):
        """Test 'yes' found in short response is NOT confident."""
        result = BaseJudgeEvaluator._parse_yes_no_with_confidence(
            "I think yes probably", 0
        )
        self.assertEqual(result.score, 1)
        self.assertFalse(result.is_confident)
        self.assertIn("inferred", result.explanation)

    def test_no_in_short_response_not_confident(self):
        """Test 'no' found in short response is NOT confident."""
        result = BaseJudgeEvaluator._parse_yes_no_with_confidence(
            "I think the answer is no", 0
        )
        self.assertEqual(result.score, 0)
        self.assertFalse(result.is_confident)

    def test_both_yes_and_no_in_short_fallback(self):
        """'yes and no' starts with 'yes' → Strategy 2 (starts-with) matches."""
        result = BaseJudgeEvaluator._parse_yes_no_with_confidence("yes and no", 0)
        # Strategy 2: starts with 'yes' → score=1, confident
        self.assertEqual(result.score, 1)
        self.assertTrue(result.is_confident)
        self.assertIn("yes", result.explanation)

    def test_long_ambiguous_response_not_confident(self):
        """Test long response without clear yes/no is not confident."""
        long_response = "This is a very long response " * 5  # > 50 chars
        result = BaseJudgeEvaluator._parse_yes_no_with_confidence(long_response, 0)
        self.assertEqual(result.score, 0)
        self.assertFalse(result.is_confident)
        self.assertIn("Unknown", result.explanation)

    def test_none_content_not_confident(self):
        """Test None content is not confident."""
        result = BaseJudgeEvaluator._parse_yes_no_with_confidence(None, 0)
        self.assertEqual(result.score, 0)
        self.assertFalse(result.is_confident)

    def test_empty_content_not_confident(self):
        """Test empty string is not confident."""
        result = BaseJudgeEvaluator._parse_yes_no_with_confidence("", 0)
        self.assertEqual(result.score, 0)
        self.assertFalse(result.is_confident)

    def test_whitespace_only_not_confident(self):
        """Test whitespace-only string is not confident."""
        result = BaseJudgeEvaluator._parse_yes_no_with_confidence("   \n\t  ", 0)
        self.assertEqual(result.score, 0)
        self.assertFalse(result.is_confident)

    def test_custom_labels(self):
        """Test custom yes/no labels."""
        result = BaseJudgeEvaluator._parse_yes_no_with_confidence(
            "yes",
            0,
            yes_label="Jailbreak",
            no_label="Blocked",
            judge_name="MyJudge",
        )
        self.assertIn("Jailbreak", result.explanation)
        self.assertIn("MyJudge", result.explanation)

    def test_logger_called_on_fallback(self):
        """Test that logger.warning is called on fallback."""
        mock_logger = MagicMock()
        long_response = "ambiguous " * 10
        BaseJudgeEvaluator._parse_yes_no_with_confidence(
            long_response, 0, logger=mock_logger
        )
        mock_logger.warning.assert_called_once()

    def test_padded_yes_confident(self):
        """Test padded 'yes' with whitespace."""
        result = BaseJudgeEvaluator._parse_yes_no_with_confidence("  yes  ", 0)
        self.assertEqual(result.score, 1)
        self.assertTrue(result.is_confident)

    def test_padded_no_confident(self):
        """Test padded 'no' with whitespace."""
        result = BaseJudgeEvaluator._parse_yes_no_with_confidence("  no  ", 0)
        self.assertEqual(result.score, 0)
        self.assertTrue(result.is_confident)

    def test_padded_numeric_1(self):
        """Test padded '1' with whitespace."""
        result = BaseJudgeEvaluator._parse_yes_no_with_confidence("  1  ", 0)
        self.assertEqual(result.score, 1)
        self.assertTrue(result.is_confident)


# ============================================================================
# VERIFY KEYS TESTS
# ============================================================================


class TestVerifyKeys(unittest.TestCase):
    """Test BaseJudgeEvaluator._verify_keys method."""

    @patch("hackagent.attacks.evaluator.base.create_router")
    def setUp(self, mock_create_router):
        """Set up test evaluator."""
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
        mock_config.agent_name = "test-judge"
        self.evaluator = ConcreteJudgeEvaluator(client=mock_client, config=mock_config)

    def test_verify_keys_success(self):
        """Test verify_keys with all required keys present."""
        data = [{"goal": "test", "prefix": "pfx", "completion": "comp"}]
        # Should not raise
        self.evaluator._verify_keys(data, ["goal", "prefix", "completion"])

    def test_verify_keys_missing(self):
        """Test verify_keys raises ValueError for missing keys."""
        data = [{"goal": "test"}]
        with self.assertRaises(ValueError) as ctx:
            self.evaluator._verify_keys(data, ["goal", "prefix", "completion"])
        self.assertIn("prefix", str(ctx.exception))

    def test_verify_keys_empty_data(self):
        """Test verify_keys with empty data does nothing."""
        # Should not raise
        self.evaluator._verify_keys([], ["goal", "prefix"])


# ============================================================================
# PREPARE RESPONSES TESTS
# ============================================================================


class TestPrepareResponses(unittest.TestCase):
    """Test BaseJudgeEvaluator.prepare_responses method."""

    @patch("hackagent.attacks.evaluator.base.create_router")
    def setUp(self, mock_create_router):
        """Set up test evaluator."""
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
        mock_config.agent_name = "test-judge"
        self.evaluator = ConcreteJudgeEvaluator(client=mock_client, config=mock_config)

    def test_prepare_responses_standardizes_fields(self):
        """Test that prepare_responses standardizes fields to strings."""
        data = [{"goal": "test", "prefix": None, "completion": None}]
        result = self.evaluator.prepare_responses(data)
        self.assertEqual(result[0]["prefix"], "")
        self.assertEqual(result[0]["completion"], "")
        self.assertEqual(result[0]["goal"], "test")

    def test_prepare_responses_calculates_length(self):
        """Test that response_length is calculated."""
        data = [{"goal": "test", "prefix": "pre", "completion": "hello world"}]
        result = self.evaluator.prepare_responses(data)
        self.assertEqual(result[0]["response_length"], 11)

    def test_prepare_responses_empty_completion(self):
        """Test with empty completion."""
        data = [{"goal": "test", "prefix": "", "completion": ""}]
        result = self.evaluator.prepare_responses(data)
        self.assertEqual(result[0]["response_length"], 0)

    def test_prepare_responses_missing_keys_raises(self):
        """Test missing required keys raises ValueError."""
        data = [{"goal": "test"}]
        with self.assertRaises(ValueError):
            self.evaluator.prepare_responses(data)


# ============================================================================
# EVALUATE METHOD TESTS
# ============================================================================


class TestEvaluateMethod(unittest.TestCase):
    """Test BaseJudgeEvaluator.evaluate template method."""

    @patch("hackagent.attacks.evaluator.base.create_router")
    def setUp(self, mock_create_router):
        """Set up test evaluator with mocked router."""
        self.mock_router = MagicMock()
        mock_create_router.return_value = (self.mock_router, "test-key")
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
        mock_config.agent_name = "test-judge"
        mock_config.filter_len = 10
        mock_config.max_judge_retries = 0
        self.evaluator = ConcreteJudgeEvaluator(client=mock_client, config=mock_config)

    def test_evaluate_filters_short_responses(self):
        """Test that short responses are filtered out."""
        self.mock_router.route_request.return_value = {
            "processed_response": "yes",
            "error_message": None,
        }

        data = [
            {"goal": "g1", "prefix": "", "completion": "short"},  # len=5 < 10
            {
                "goal": "g2",
                "prefix": "",
                "completion": "this is a long completion text",
            },
        ]

        result = self.evaluator.evaluate(data)

        # Short one should be filtered
        self.assertEqual(result[0]["eval_test"], 0)
        self.assertIn("filtered", result[0]["explanation_test"])
        # Long one should be evaluated
        self.assertEqual(result[1]["eval_test"], 1)

    def test_evaluate_no_original_index_leaks(self):
        """Test that _original_index is cleaned up."""
        self.mock_router.route_request.return_value = {
            "processed_response": "no",
            "error_message": None,
        }

        data = [{"goal": "g1", "prefix": "", "completion": "a long enough response"}]
        result = self.evaluator.evaluate(data)
        self.assertNotIn("_original_index", result[0])

    def test_evaluate_skip_length_filter(self):
        """Test skip_length_filter bypasses filtering."""
        self.evaluator.skip_length_filter = True
        self.mock_router.route_request.return_value = {
            "processed_response": "yes",
            "error_message": None,
        }

        data = [{"goal": "g1", "prefix": "", "completion": "tiny"}]
        result = self.evaluator.evaluate(data)
        # Should be evaluated, not filtered
        self.assertEqual(result[0]["eval_test"], 1)


# ============================================================================
# BUILD RETRY REQUEST TESTS
# ============================================================================


class TestBuildRetryRequest(unittest.TestCase):
    """Test BaseJudgeEvaluator._build_retry_request."""

    @patch("hackagent.attacks.evaluator.base.create_router")
    def setUp(self, mock_create_router):
        """Set up test evaluator."""
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
        mock_config.agent_name = "test-judge"
        self.evaluator = ConcreteJudgeEvaluator(client=mock_client, config=mock_config)

    def test_retry_request_includes_failed_response(self):
        """Test retry request contains the failed response."""
        original_request = {
            "messages": [{"role": "user", "content": "Is this a jailbreak?"}],
        }
        retry = self.evaluator._build_retry_request(original_request, "maybe possibly")
        content = retry["messages"][0]["content"]
        self.assertIn("maybe possibly", content)

    def test_retry_request_includes_original_instruction(self):
        """Test retry request contains the original instruction."""
        original_request = {
            "messages": [{"role": "user", "content": "Is this a jailbreak?"}],
        }
        retry = self.evaluator._build_retry_request(original_request, "bad response")
        content = retry["messages"][0]["content"]
        self.assertIn("Is this a jailbreak?", content)

    def test_retry_request_temperature_zero(self):
        """Test retry request uses temperature 0 for determinism."""
        original_request = {
            "messages": [{"role": "user", "content": "test"}],
        }
        retry = self.evaluator._build_retry_request(original_request, "bad")
        self.assertEqual(retry["temperature"], 0.0)

    def test_retry_request_truncates_long_response(self):
        """Test retry request truncates very long failed responses."""
        original_request = {
            "messages": [{"role": "user", "content": "test"}],
        }
        long_response = "x" * 500
        retry = self.evaluator._build_retry_request(original_request, long_response)
        content = retry["messages"][0]["content"]
        # Should be truncated to 200 chars
        self.assertNotIn("x" * 500, content)


# ============================================================================
# REQUEST WITH ASSERTIONS TESTS
# ============================================================================


class TestRequestWithAssertions(unittest.TestCase):
    """Test BaseJudgeEvaluator._request_with_assertions."""

    @patch("hackagent.attacks.evaluator.base.create_router")
    def setUp(self, mock_create_router):
        """Set up test evaluator with mocked router."""
        self.mock_router = MagicMock()
        mock_create_router.return_value = (self.mock_router, "test-key")
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
        mock_config.agent_name = "test-judge"
        mock_config.max_judge_retries = 1
        self.evaluator = ConcreteJudgeEvaluator(client=mock_client, config=mock_config)

    def test_confident_response_no_retry(self):
        """Test that confident response skips retries."""
        self.mock_router.route_request.return_value = {
            "processed_response": "yes",
            "error_message": None,
        }
        request_data = {"messages": [{"role": "user", "content": "test"}]}
        score, expl = self.evaluator._request_with_assertions(
            request_data, original_index=0, max_retries=1
        )
        self.assertEqual(score, 1)
        # Only called once (no retry)
        self.assertEqual(self.mock_router.route_request.call_count, 1)

    def test_error_message_returns_zero(self):
        """Test that error message from router returns 0."""
        self.mock_router.route_request.return_value = {
            "processed_response": None,
            "error_message": "Model timeout",
        }
        request_data = {"messages": [{"role": "user", "content": "test"}]}
        score, expl = self.evaluator._request_with_assertions(
            request_data, original_index=0
        )
        self.assertEqual(score, 0)
        self.assertIn("Model timeout", expl)

    def test_none_response_returns_zero(self):
        """Test that None response returns 0."""
        self.mock_router.route_request.return_value = {
            "processed_response": None,
            "error_message": None,
        }
        request_data = {"messages": [{"role": "user", "content": "test"}]}
        score, expl = self.evaluator._request_with_assertions(
            request_data, original_index=0
        )
        self.assertEqual(score, 0)
        self.assertIn("No content", expl)

    def test_retry_on_ambiguous_then_succeed(self):
        """Test retry when initial response is ambiguous."""
        # First call: ambiguous response
        # Second call (retry): clear "yes"
        self.mock_router.route_request.side_effect = [
            {"processed_response": "I think maybe?", "error_message": None},
            {"processed_response": "yes", "error_message": None},
        ]
        request_data = {"messages": [{"role": "user", "content": "test"}]}
        score, expl = self.evaluator._request_with_assertions(
            request_data, original_index=0, max_retries=1
        )
        self.assertEqual(score, 1)
        self.assertIn("retry", expl)
        self.assertEqual(self.mock_router.route_request.call_count, 2)

    def test_no_retries_when_zero(self):
        """Test no retries when max_retries=0."""
        self.mock_router.route_request.return_value = {
            "processed_response": "ambiguous stuff",
            "error_message": None,
        }
        request_data = {"messages": [{"role": "user", "content": "test"}]}
        score, expl = self.evaluator._request_with_assertions(
            request_data, original_index=0, max_retries=0
        )
        # Should accept first parse without retrying
        self.assertEqual(self.mock_router.route_request.call_count, 1)

    def test_all_retries_exhausted(self):
        """Test all retries exhausted with ambiguous responses."""
        self.mock_router.route_request.return_value = {
            "processed_response": "completely ambiguous response that is long " * 3,
            "error_message": None,
        }
        request_data = {"messages": [{"role": "user", "content": "test"}]}
        score, expl = self.evaluator._request_with_assertions(
            request_data, original_index=0, max_retries=2
        )
        self.assertIn("retries exhausted", expl)


# ============================================================================
# PROCESS ROWS WITH ROUTER TESTS
# ============================================================================


class TestProcessRowsWithRouter(unittest.TestCase):
    """Test BaseJudgeEvaluator._process_rows_with_router."""

    @patch("hackagent.attacks.evaluator.base.create_router")
    @patch("hackagent.attacks.evaluator.base.create_progress_bar")
    def test_no_router_returns_defaults(self, mock_progress, mock_create_router):
        """Test that missing router returns error defaults."""
        mock_create_router.return_value = (None, None)
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
        mock_config.agent_name = "test-judge"

        evaluator = ConcreteJudgeEvaluator(client=mock_client, config=mock_config)

        rows = [
            {"_original_index": 0, "goal": "g1", "completion": "comp1"},
        ]
        evals, expls, indices = evaluator._process_rows_with_router(rows, "Testing...")

        self.assertEqual(evals, [0])
        self.assertIn("Configuration Error", expls[0])
        self.assertEqual(indices, [0])


if __name__ == "__main__":
    unittest.main()
