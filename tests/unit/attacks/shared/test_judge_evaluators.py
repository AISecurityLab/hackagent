# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for shared judge_evaluators module.

Focuses on the shared yes/no parser and the template-method evaluate()
since the full evaluator pipeline requires AgentRouter integration.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from hackagent.attacks.evaluator import (
    AssertionResult,
    BaseJudgeEvaluator,
    NuancedEvaluator,
    JailbreakBenchEvaluator,
    HarmBenchEvaluator,
    EVALUATOR_MAP,
)


@pytest.fixture
def logger():
    return logging.getLogger("test.judge_evaluators")


class TestParseYesNoResponse:
    """Tests for the shared _parse_yes_no_response static method."""

    def test_direct_yes(self):
        score, expl = BaseJudgeEvaluator._parse_yes_no_response("yes", 0)
        assert score == 1
        assert "yes" in expl.lower()

    def test_direct_no(self):
        score, expl = BaseJudgeEvaluator._parse_yes_no_response("no", 0)
        assert score == 0
        assert "no" in expl.lower()

    def test_yes_case_insensitive(self):
        score, _ = BaseJudgeEvaluator._parse_yes_no_response("YES", 0)
        assert score == 1

    def test_no_case_insensitive(self):
        score, _ = BaseJudgeEvaluator._parse_yes_no_response("NO", 0)
        assert score == 0

    def test_yes_with_trailing_text(self):
        score, expl = BaseJudgeEvaluator._parse_yes_no_response(
            "yes, this is clearly harmful", 0
        )
        assert score == 1
        assert "extracted" in expl.lower()

    def test_no_with_trailing_text(self):
        score, expl = BaseJudgeEvaluator._parse_yes_no_response(
            "no, this is safe content", 0
        )
        assert score == 0
        assert "extracted" in expl.lower()

    def test_yes_inferred_short_response(self):
        score, expl = BaseJudgeEvaluator._parse_yes_no_response("I think yes", 0)
        assert score == 1
        assert "inferred" in expl.lower()

    def test_no_inferred_short_response(self):
        score, expl = BaseJudgeEvaluator._parse_yes_no_response("definitely no", 0)
        assert score == 0
        assert "inferred" in expl.lower()

    def test_ambiguous_short_response(self):
        """Response starting with 'yes' is extracted, even if 'no' appears later."""
        score, expl = BaseJudgeEvaluator._parse_yes_no_response("yes and no", 0)
        # Strategy 2 (starts-with) matches "yes" first
        assert score == 1
        assert "extracted" in expl.lower()

    def test_long_ambiguous_response(self):
        """Long response without clear yes/no defaults to 0."""
        long_text = "This is a response that does not contain clear answers " * 5
        score, expl = BaseJudgeEvaluator._parse_yes_no_response(long_text, 0)
        assert score == 0
        assert "Unknown" in expl

    def test_none_content(self):
        score, expl = BaseJudgeEvaluator._parse_yes_no_response(None, 0)
        assert score == 0
        assert "No content" in expl

    def test_custom_labels(self):
        score, expl = BaseJudgeEvaluator._parse_yes_no_response(
            "yes",
            0,
            yes_label="Jailbreak successful",
            no_label="No jailbreak",
            judge_name="JailbreakBench",
        )
        assert score == 1
        assert "Jailbreak successful" in expl
        assert "JailbreakBench" in expl

    def test_whitespace_handling(self):
        score, _ = BaseJudgeEvaluator._parse_yes_no_response("  yes  ", 0)
        assert score == 1

    def test_empty_string(self):
        score, expl = BaseJudgeEvaluator._parse_yes_no_response("", 0)
        assert score == 0


class TestEvaluatorMap:
    """Tests for the EVALUATOR_MAP registry."""

    def test_map_has_three_entries(self):
        assert len(EVALUATOR_MAP) == 3

    def test_nuanced_in_map(self):
        assert "nuanced" in EVALUATOR_MAP
        assert EVALUATOR_MAP["nuanced"] is NuancedEvaluator

    def test_jailbreakbench_in_map(self):
        assert "jailbreakbench" in EVALUATOR_MAP
        assert EVALUATOR_MAP["jailbreakbench"] is JailbreakBenchEvaluator

    def test_harmbench_in_map(self):
        assert "harmbench" in EVALUATOR_MAP
        assert EVALUATOR_MAP["harmbench"] is HarmBenchEvaluator


class TestEvaluatorClassAttributes:
    """Tests for evaluator class-level configuration."""

    def test_nuanced_columns(self):
        assert NuancedEvaluator.eval_column == "eval_nj"
        assert NuancedEvaluator.explanation_column == "explanation_nj"
        assert NuancedEvaluator.skip_length_filter is False

    def test_jailbreakbench_columns(self):
        assert JailbreakBenchEvaluator.eval_column == "eval_jb"
        assert JailbreakBenchEvaluator.explanation_column == "explanation_jb"
        assert JailbreakBenchEvaluator.skip_length_filter is False

    def test_harmbench_columns(self):
        assert HarmBenchEvaluator.eval_column == "eval_hb"
        assert HarmBenchEvaluator.explanation_column == "explanation_hb"
        assert HarmBenchEvaluator.skip_length_filter is True

    def test_nuanced_prompt_has_placeholders(self):
        assert "{request}" in NuancedEvaluator.PROMPT
        assert "{response}" in NuancedEvaluator.PROMPT

    def test_jailbreakbench_prompt_has_placeholders(self):
        assert "{generation}" in JailbreakBenchEvaluator.PROMPT

    def test_harmbench_prompt_has_placeholders(self):
        assert "{behavior}" in HarmBenchEvaluator.PROMPT
        assert "{generation}" in HarmBenchEvaluator.PROMPT


class TestReExports:
    """Tests that advprefix/evaluators.py re-exports work correctly."""

    def test_base_evaluator_alias(self):
        from hackagent.attacks.evaluator import BaseJudgeEvaluator as BaseEvaluator

        assert BaseEvaluator is BaseJudgeEvaluator

    def test_nuanced_reexport(self):
        from hackagent.attacks.evaluator import (
            NuancedEvaluator as NE,
        )

        assert NE is NuancedEvaluator

    def test_jailbreakbench_reexport(self):
        from hackagent.attacks.evaluator import (
            JailbreakBenchEvaluator as JB,
        )

        assert JB is JailbreakBenchEvaluator

    def test_harmbench_reexport(self):
        from hackagent.attacks.evaluator import (
            HarmBenchEvaluator as HB,
        )

        assert HB is HarmBenchEvaluator

    def test_evaluator_map_reexport(self):
        from hackagent.attacks.evaluator import (
            EVALUATOR_MAP as MAP,
        )

        assert MAP is EVALUATOR_MAP


# ============================================================================
# DSPy-INSPIRED ASSERTION & RETRY MECHANISM TESTS
# ============================================================================


class TestAssertionResult:
    """Tests for the AssertionResult dataclass."""

    def test_create_confident(self):
        r = AssertionResult(score=1, explanation="yes", is_confident=True)
        assert r.score == 1
        assert r.explanation == "yes"
        assert r.is_confident is True

    def test_create_not_confident(self):
        r = AssertionResult(score=0, explanation="Unknown", is_confident=False)
        assert r.score == 0
        assert r.is_confident is False

    def test_is_frozen(self):
        r = AssertionResult(score=1, explanation="yes", is_confident=True)
        with pytest.raises(AttributeError):
            r.score = 2  # type: ignore[misc]


class TestParseYesNoWithConfidence:
    """Tests for _parse_yes_no_with_confidence returning AssertionResult."""

    def test_direct_yes_is_confident(self):
        r = BaseJudgeEvaluator._parse_yes_no_with_confidence("yes", 0)
        assert r.score == 1
        assert r.is_confident is True

    def test_direct_no_is_confident(self):
        r = BaseJudgeEvaluator._parse_yes_no_with_confidence("no", 0)
        assert r.score == 0
        assert r.is_confident is True

    def test_starts_with_yes_is_confident(self):
        r = BaseJudgeEvaluator._parse_yes_no_with_confidence("yes, it is harmful", 0)
        assert r.score == 1
        assert r.is_confident is True

    def test_inferred_yes_not_confident(self):
        r = BaseJudgeEvaluator._parse_yes_no_with_confidence("I think yes", 0)
        assert r.score == 1
        assert r.is_confident is False

    def test_numeric_one_is_confident(self):
        r = BaseJudgeEvaluator._parse_yes_no_with_confidence("1", 0)
        assert r.score == 1
        assert r.is_confident is True

    def test_numeric_zero_is_confident(self):
        r = BaseJudgeEvaluator._parse_yes_no_with_confidence("0", 0)
        assert r.score == 0
        assert r.is_confident is True

    def test_gibberish_not_confident(self):
        r = BaseJudgeEvaluator._parse_yes_no_with_confidence(
            "1.  **An explanation**", 0
        )
        assert r.is_confident is False

    def test_none_not_confident(self):
        r = BaseJudgeEvaluator._parse_yes_no_with_confidence(None, 0)
        assert r.score == 0
        assert r.is_confident is False

    def test_long_ambiguous_not_confident(self):
        text = "This response does not indicate a clear verdict " * 5
        r = BaseJudgeEvaluator._parse_yes_no_with_confidence(text, 0)
        assert r.score == 0
        assert r.is_confident is False


class TestNumericParsing:
    """Tests for numeric '1'/'0' parsing (Strategy 3)."""

    def test_bare_one(self):
        score, expl = BaseJudgeEvaluator._parse_yes_no_response("1", 0)
        assert score == 1

    def test_bare_zero(self):
        score, expl = BaseJudgeEvaluator._parse_yes_no_response("0", 0)
        assert score == 0

    def test_one_with_whitespace(self):
        score, _ = BaseJudgeEvaluator._parse_yes_no_response("  1  ", 0)
        assert score == 1

    def test_zero_with_whitespace(self):
        score, _ = BaseJudgeEvaluator._parse_yes_no_response("  0  ", 0)
        assert score == 0

    def test_not_standalone_number(self):
        """'10' should NOT match numeric strategy."""
        r = BaseJudgeEvaluator._parse_yes_no_with_confidence("10", 0)
        # '10' is not a bare '1' or '0'
        assert r.is_confident is False


class TestBuildRetryRequest:
    """Tests for _build_retry_request method."""

    @pytest.fixture
    def mock_evaluator(self):
        """Create a minimal BaseJudgeEvaluator for testing (mock ABC)."""
        # Patch the abstract methods so we can instantiate
        with patch.multiple(
            BaseJudgeEvaluator,
            __abstractmethods__=set(),
            _get_request_data_for_row=MagicMock(return_value={}),
            _parse_response_content=MagicMock(return_value=(0, "test")),
        ):
            config = MagicMock()
            config.agent_name = "test-judge"
            config.model_id = "test-model"
            config.max_new_tokens_eval = 512
            config.temperature = 0.0
            config.max_judge_retries = 1
            evaluator = BaseJudgeEvaluator.__new__(BaseJudgeEvaluator)
            evaluator.config = config
            evaluator.logger = logging.getLogger("test")
            return evaluator

    def test_retry_request_has_feedback(self, mock_evaluator):
        original = {
            "messages": [{"role": "user", "content": "Is this harmful? yes or no"}],
            "max_tokens": 5,
            "temperature": 0.0,
        }
        retry = mock_evaluator._build_retry_request(original, "1.  **An explanation**")
        messages = retry["messages"]
        assert len(messages) == 1
        assert "1.  **An explanation**" in messages[0]["content"]
        assert "yes" in messages[0]["content"].lower()
        assert "no" in messages[0]["content"].lower()

    def test_retry_request_preserves_constraints(self, mock_evaluator):
        original = {
            "messages": [{"role": "user", "content": "Judge this"}],
            "max_tokens": 5,
            "temperature": 0.5,
        }
        retry = mock_evaluator._build_retry_request(original, "bad response")
        # _build_retry_request uses config.max_new_tokens_eval, not the original max_tokens
        assert retry["max_tokens"] == mock_evaluator.config.max_new_tokens_eval
        assert retry["temperature"] == 0.0

    def test_retry_includes_original_instruction(self, mock_evaluator):
        original_content = "Is this harmful? Answer yes or no."
        original = {
            "messages": [{"role": "user", "content": original_content}],
        }
        retry = mock_evaluator._build_retry_request(original, "maybe")
        assert original_content in retry["messages"][0]["content"]


class TestCheckAssertion:
    """Tests for _check_assertion on different evaluator types."""

    def test_base_yes_no_confident(self):
        r = BaseJudgeEvaluator._parse_yes_no_with_confidence("yes", 0)
        assert r.is_confident is True

    def test_nuanced_violating_confident(self):
        with patch.multiple(
            NuancedEvaluator,
            __abstractmethods__=set(),
        ):
            evaluator = NuancedEvaluator.__new__(NuancedEvaluator)
            evaluator.logger = logging.getLogger("test")
            r = evaluator._check_assertion("1_violating", 0)
            assert r.is_confident is True
            assert r.score == 1

    def test_nuanced_compliant_confident(self):
        with patch.multiple(
            NuancedEvaluator,
            __abstractmethods__=set(),
        ):
            evaluator = NuancedEvaluator.__new__(NuancedEvaluator)
            evaluator.logger = logging.getLogger("test")
            r = evaluator._check_assertion("0_compliant", 0)
            assert r.is_confident is True
            assert r.score == 0

    def test_nuanced_unknown_not_confident(self):
        with patch.multiple(
            NuancedEvaluator,
            __abstractmethods__=set(),
        ):
            evaluator = NuancedEvaluator.__new__(NuancedEvaluator)
            evaluator.logger = logging.getLogger("test")
            r = evaluator._check_assertion("some gibberish", 0)
            assert r.is_confident is False


class TestRequestWithAssertions:
    """Tests for the full assert-and-retry loop."""

    @pytest.fixture
    def evaluator_with_router(self):
        """Create an evaluator with a mocked AgentRouter."""
        with patch.multiple(
            HarmBenchEvaluator,
            __abstractmethods__=set(),
        ):
            evaluator = HarmBenchEvaluator.__new__(HarmBenchEvaluator)
            evaluator.agent_router = MagicMock()
            evaluator.agent_registration_key = "test-key"
            evaluator.logger = logging.getLogger("test")
            config = MagicMock()
            config.agent_name = "test-judge"
            config.model_id = "test-model"
            config.max_new_tokens_eval = 512
            config.temperature = 0.0
            config.max_judge_retries = 1
            evaluator.config = config
            return evaluator

    def test_confident_first_try_no_retry(self, evaluator_with_router):
        """When the first response is confident, no retry should occur."""
        evaluator_with_router.agent_router.route_request.return_value = {
            "processed_response": "yes",
        }
        request_data = {
            "messages": [{"role": "user", "content": "test"}],
            "max_tokens": 5,
        }
        score, expl = evaluator_with_router._request_with_assertions(
            request_data=request_data, original_index=0, max_retries=1
        )
        assert score == 1
        # Router should be called exactly once (no retry)
        assert evaluator_with_router.agent_router.route_request.call_count == 1

    def test_retry_succeeds_on_second_try(self, evaluator_with_router):
        """When first response is gibberish and retry returns 'yes'."""
        evaluator_with_router.agent_router.route_request.side_effect = [
            {"processed_response": "1.  **An explanation**"},
            {"processed_response": "yes"},
        ]
        request_data = {
            "messages": [{"role": "user", "content": "test"}],
            "max_tokens": 5,
        }
        score, expl = evaluator_with_router._request_with_assertions(
            request_data=request_data, original_index=0, max_retries=1
        )
        assert score == 1
        assert "retry" in expl.lower()
        assert evaluator_with_router.agent_router.route_request.call_count == 2

    def test_retries_exhausted_returns_fallback(self, evaluator_with_router):
        """When all retries produce gibberish, returns fallback score 0."""
        evaluator_with_router.agent_router.route_request.side_effect = [
            {"processed_response": "garbage response"},
            {"processed_response": "still garbage"},
        ]
        request_data = {
            "messages": [{"role": "user", "content": "test"}],
            "max_tokens": 5,
        }
        score, expl = evaluator_with_router._request_with_assertions(
            request_data=request_data, original_index=0, max_retries=1
        )
        assert score == 0
        assert "retries exhausted" in expl.lower()

    def test_zero_retries_skips_retry_loop(self, evaluator_with_router):
        """When max_retries=0, no retry even with low confidence."""
        evaluator_with_router.agent_router.route_request.return_value = {
            "processed_response": "garbage",
        }
        request_data = {
            "messages": [{"role": "user", "content": "test"}],
            "max_tokens": 5,
        }
        score, expl = evaluator_with_router._request_with_assertions(
            request_data=request_data, original_index=0, max_retries=0
        )
        assert evaluator_with_router.agent_router.route_request.call_count == 1

    def test_router_error_returns_error_message(self, evaluator_with_router):
        """When the router returns an error, no retry and error propagated."""
        evaluator_with_router.agent_router.route_request.return_value = {
            "error_message": "connection refused",
            "processed_response": None,
        }
        request_data = {
            "messages": [{"role": "user", "content": "test"}],
            "max_tokens": 5,
        }
        score, expl = evaluator_with_router._request_with_assertions(
            request_data=request_data, original_index=0, max_retries=1
        )
        assert score == 0
        assert "connection refused" in expl

    def test_retry_with_numeric_one(self, evaluator_with_router):
        """Retry returning '1' should be parsed as confident yes."""
        evaluator_with_router.agent_router.route_request.side_effect = [
            {"processed_response": "maybe harmful"},
            {"processed_response": "1"},
        ]
        request_data = {
            "messages": [{"role": "user", "content": "test"}],
            "max_tokens": 5,
        }
        score, expl = evaluator_with_router._request_with_assertions(
            request_data=request_data, original_index=0, max_retries=1
        )
        assert score == 1
        assert "retry" in expl.lower()
