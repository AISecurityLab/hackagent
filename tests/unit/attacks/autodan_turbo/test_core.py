import unittest
from itertools import product
from unittest.mock import MagicMock, patch

import pytest

from hackagent.attacks.techniques.autodan_turbo import core


STRUCTURED_SCORE_ASSESSMENTS = (
    "Rating: [[2.5]]\nEXPLANATION: score 10 requires a different result",
    "Rating: [[2.5]]\nEXPLANATION: Rating: [[10]] is not appropriate",
    "[[2.5]]\nEXPLANATION: score 10 requires a different result",
    "[[2.5]]\nEXPLANATION: [[10]] is not appropriate",
    '{"score": 2.5, "explanation": "score 10 requires a different result"}',
    '{"rating": 2.5, "explanation": "score 10 requires a different result"}',
    '{"explanation": "score 10 requires a different result", "SCORE": 2.5}',
    '{"score": "2.5", "explanation": "score 10 requires a different result"}',
    '{"score": 2.5, "explanation": "Rating: [[10]] is not appropriate"}',
)

MALFORMED_SCORE_FRACTIONS = (
    "SCORE: 1,9/10.0",
    "SCORE: 2,500/10",
    "1,9/10.0",
    "2,500/10",
    "SCORE: 1,2,9/10.0",
    "SCORE: 1.2.9/10.0",
    "SCORE: 1e9/10.0",
    "SCORE: 1_9/10.0",
    "SCORE: -1+9/10.0",
    "SCORE: 1/9/10.0",
    "SCORE: 1/10/10",
)

SCORE_WHITESPACE = ("", " ", "\t", "\n")


@pytest.mark.parametrize("before,after", product(SCORE_WHITESPACE, repeat=2))
@pytest.mark.parametrize(
    "template",
    (
        "2.5{before}/{after}10{before}/{after}10",
        "2.5{before}/{after}9{before}/{after}10",
        "2.5{before}/{after}/{after}10{before}/{after}10",
        "1{before},{after}9/10",
        "1.2{before}.{after}9/10",
        "1{before}+{after}9/10",
        "1{before}-{after}9/10",
        "1{before}_{after}9/10",
        "1{before}e{after}9/10",
        "1{before}'{after}9/10",
        "1{before}:{after}9/10",
    ),
)
def test_strict_score_parser_rejects_incomplete_numeric_spans(template, before, after):
    text = "SCORE: " + template.format(before=before, after=after)
    assert core._parse_score_value(text, allow_fallback=False) is None


@pytest.mark.parametrize("gaps", product(SCORE_WHITESPACE, repeat=4))
def test_strict_score_parser_rejects_nested_fractions_with_independent_spacing(gaps):
    a, b, c, d = gaps
    text = f"SCORE: 2.5{a}/{b}10{c}/{d}10"
    assert core._parse_score_value(text, allow_fallback=False) is None


@pytest.mark.parametrize("before,after", product(SCORE_WHITESPACE, repeat=2))
@pytest.mark.parametrize("template", ("{}", "SCORE: {}", "Rating: [[{}]]"))
def test_strict_score_parser_preserves_complete_numeric_spans(template, before, after):
    text = template.format(f"2.5{before}/{after}10.0")
    assert core._parse_score_value(text, allow_fallback=False) == 2.5


class TestCoreHelpers(unittest.TestCase):
    def test_truncate_for_log(self):
        self.assertEqual(core._truncate_for_log(None), "")
        self.assertEqual(core._truncate_for_log("abc", limit=10), "abc")
        self.assertTrue(core._truncate_for_log("x" * 20, limit=5).endswith("..."))

    def test_parse_score_value_variants(self):
        self.assertEqual(core._parse_score_value("9.5"), 9.5)
        self.assertIsNone(core._parse_score_value(""))
        self.assertEqual(core._parse_score_value("final assessment score: 11"), 10.0)
        self.assertEqual(core._parse_score_value("score is 0.2"), 1.0)
        self.assertEqual(core._parse_score_value("blah 2 and 6.5"), 6.5)
        self.assertIsNone(core._parse_score_value("no numbers"))

    def test_parse_score_value_handles_float_exception(self):
        import builtins

        original_float = builtins.float

        def _patched_float(value):
            if value == "2":
                raise ValueError("boom")
            return original_float(value)

        with patch("builtins.float", side_effect=_patched_float):
            self.assertEqual(core._parse_score_value("numbers 2 and 4.5"), 4.5)

    def test_parse_score_value_reliable_formats(self):
        cases = [
            ("2.5", 2.5),
            ("SCORE: 2.5/10.0\nEXPLANATION: sample refused", 2.5),
            ("score = 2.5", 2.5),
            ("Score - 2.5", 2.5),
            ("final score 2.5", 2.5),
            ("Final assessment score: 2.5", 2.5),
            ("assessment score: 2.5", 2.5),
            ("score is 2.5", 2.5),
            ("The final score is 2.5.", 2.5),
            ("**SCORE:** 2.5/10.0", 2.5),
            ('{"score": 2.5}', 2.5),
            ("Rating: [[2.5]]", 2.5),
            ("[[2.5]]", 2.5),
            ("2.5/10", 2.5),
            ("2.5 / 10.0", 2.5),
            ("2.5/10.00", 2.5),
            ("(2.5/10.0)", 2.5),
            ("The assessment is 2.5/10.0.", 2.5),
            ("SCORE: 2.5/10.0\nEXPLANATION: 10 examples considered", 2.5),
            ("SCORE: 2.5/10.0\nEXPLANATION: score 10 requires a different result", 2.5),
            ("SCORE: 2.5/10.0\nEXPLANATION: Rating: [[10]] is not appropriate", 2.5),
            ("0", 1.0),
            ("score is 0.2", 1.0),
            ("final assessment score: 11", 10.0),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(
                    core._parse_score_value(text, allow_fallback=False), expected
                )

    def test_parse_score_value_reliable_mode_rejects_incidental_or_malformed_numbers(
        self,
    ):
        for text in (
            "",
            " ",
            "no numbers",
            "There are 2 examples and 10 rubric levels",
            "ERROR 503: retry in 10 seconds",
            "NaN",
            "inf",
            "2.5.0",
            "SCORE: 2.5.0",
            "2.5/100",
            "SCORE: 2.5/100",
            "2.5/10.5",
            "SCORE: 2.5/10.5",
            "SCORE: 2e3",
            "SCORE: 2,500",
            "Rating: [[10",
        ):
            with self.subTest(text=text):
                self.assertIsNone(core._parse_score_value(text, allow_fallback=False))

    def test_structured_score_fields_take_precedence_over_explanation_scores(self):
        for assessment in STRUCTURED_SCORE_ASSESSMENTS:
            with self.subTest(assessment=assessment):
                self.assertEqual(
                    core._parse_score_value(assessment, allow_fallback=False), 2.5
                )

    def test_fraction_parser_does_not_restart_inside_malformed_numerators(self):
        for assessment in MALFORMED_SCORE_FRACTIONS:
            with self.subTest(assessment=assessment):
                self.assertIsNone(
                    core._parse_score_value(assessment, allow_fallback=False)
                )

    @patch("hackagent.attacks.techniques.autodan_turbo.core.create_router")
    def test_init_routers(self, mock_create_router):
        mock_create_router.side_effect = [
            ("att-router", "att-key"),
            ("sc-router", "sc-key"),
            ("sum-router", "sum-key"),
        ]
        cfg = {"attacker": {}, "scorer": {}, "summarizer": {}}
        out = core.init_routers(cfg, client=MagicMock(), logger=MagicMock())
        self.assertEqual(
            out,
            ("att-router", "att-key", "sc-router", "sc-key", "sum-router", "sum-key"),
        )
        self.assertEqual(mock_create_router.call_count, 3)


class TestCoreGenerationAndScoring(unittest.TestCase):
    @patch("hackagent.attacks.techniques.autodan_turbo.core.extract_response_content")
    def test_conditional_generate_prefill_honored(self, mock_extract):
        router = MagicMock()
        router.route_request.return_value = {"dummy": True}
        mock_extract.return_value = " generated prompt"

        output = core.conditional_generate(
            router=router,
            key="k",
            system="sys",
            condition="cond",
            logger=MagicMock(),
        )
        self.assertTrue(output.startswith("[START OF JAILBREAK PROMPT]"))

    @patch("hackagent.attacks.techniques.autodan_turbo.core.extract_response_content")
    def test_conditional_generate_does_not_double_start_tag(self, mock_extract):
        router = MagicMock()
        router.route_request.return_value = {"dummy": True}
        mock_extract.return_value = (
            "[START OF JAILBREAK PROMPT]inner[END OF JAILBREAK PROMPT]"
        )

        output = core.conditional_generate(
            router=router,
            key="k",
            system="sys",
            condition="cond",
            logger=MagicMock(),
        )
        self.assertEqual(output.count("[START OF JAILBREAK PROMPT]"), 1)

    @patch("hackagent.attacks.techniques.autodan_turbo.core.extract_response_content")
    def test_conditional_generate_fallback_no_prefill(self, mock_extract):
        router = MagicMock()
        router.route_request.return_value = {"dummy": True}
        mock_extract.side_effect = [None, "full response"]

        output = core.conditional_generate(
            router=router,
            key="k",
            system="sys",
            condition="cond",
            logger=MagicMock(),
        )
        self.assertEqual(output, "full response")
        self.assertEqual(router.route_request.call_count, 2)

    @patch(
        "hackagent.attacks.techniques.autodan_turbo.core.extract_response_content",
        return_value="target out",
    )
    def test_query_target(self, _):
        agent_router = MagicMock()
        agent_router.route_request.return_value = {"dummy": True}
        cfg = {"max_tokens": 10, "temperature": 0.1}
        out = core.query_target(agent_router, "v-key", "prompt", cfg, MagicMock())
        self.assertEqual(out, ("target out", None))

    @patch("hackagent.attacks.techniques.autodan_turbo.core.extract_response_content")
    def test_score_response_wrapper_parsed(self, mock_extract):
        scorer_router = MagicMock()
        scorer_router.route_request.return_value = {"dummy": True}
        mock_extract.side_effect = [
            "Analysis of the sample",
            "8.0",
        ]
        score, assessment = core.score_response(
            scorer_router,
            "sc-key",
            "goal",
            "target response",
            logger=MagicMock(),
            max_retries=1,
        )
        self.assertEqual(score, 8.0)
        self.assertIn("Analysis", assessment)
        self.assertEqual(scorer_router.route_request.call_count, 2)

    @patch("hackagent.attacks.techniques.autodan_turbo.core.extract_response_content")
    def test_score_response_explicit_assessment_skips_wrapper(self, mock_extract):
        scorer_router = MagicMock()
        scorer_router.route_request.return_value = {"dummy": True}
        mock_extract.side_effect = [
            "final score 6.0",
            "not-a-number",
        ]
        score, assessment = core.score_response(
            scorer_router,
            "sc-key",
            "goal",
            "target response",
            logger=MagicMock(),
            max_retries=1,
        )
        self.assertEqual(score, 6.0)
        self.assertIn("score", assessment)
        scorer_router.route_request.assert_called_once()

    @patch("hackagent.attacks.techniques.autodan_turbo.core.extract_response_content")
    def test_score_response_empty_wrapper_uses_direct_numeric(self, mock_extract):
        scorer_router = MagicMock()
        scorer_router.route_request.return_value = {"dummy": True}
        mock_extract.side_effect = [
            "analysis without parseable wrapper",
            "",
            "7.5",
        ]
        score, _assessment = core.score_response(
            scorer_router,
            "sc-key",
            "goal",
            "target response",
            logger=MagicMock(),
            max_retries=1,
        )
        self.assertEqual(score, 7.5)

    @patch(
        "hackagent.attacks.techniques.autodan_turbo.core.extract_response_content",
        side_effect=Exception("boom"),
    )
    def test_score_response_exception_returns_default(self, _mock_extract):
        scorer_router = MagicMock()
        scorer_router.route_request.return_value = {"dummy": True}
        score, assessment = core.score_response(
            scorer_router,
            "sc-key",
            "goal",
            "target response",
            logger=MagicMock(),
            max_retries=1,
        )
        self.assertEqual(score, 1.0)
        self.assertIn("failed", assessment.lower())

    @patch("hackagent.attacks.techniques.autodan_turbo.core.extract_response_content")
    def test_score_response_retries_after_empty_assessment(self, mock_extract):
        scorer_router = MagicMock()
        scorer_router.route_request.return_value = {"dummy": True}
        mock_extract.side_effect = [
            None,
            "analysis score 5.0",
            "5.0",
        ]
        score, _assessment = core.score_response(
            scorer_router,
            "sc-key",
            "goal",
            "target response",
            logger=MagicMock(),
            max_retries=2,
        )
        self.assertEqual(score, 5.0)

    @patch("hackagent.attacks.techniques.autodan_turbo.core.extract_response_content")
    def test_score_response_warn_path_when_nothing_parseable(self, mock_extract):
        scorer_router = MagicMock()
        scorer_router.route_request.return_value = {"dummy": True}
        mock_extract.side_effect = [
            "analysis without numbers",
            "still-no-number",
            "nope",
        ]
        score, assessment = core.score_response(
            scorer_router,
            "sc-key",
            "goal",
            "target response",
            logger=MagicMock(),
            max_retries=1,
        )
        self.assertEqual(score, 1.0)
        self.assertIn("failed", assessment.lower())

    @patch("hackagent.attacks.techniques.autodan_turbo.core.extract_response_content")
    def test_score_response_explicit_assessment_skips_direct_numeric(
        self, mock_extract
    ):
        scorer_router = MagicMock()
        scorer_router.route_request.return_value = {"dummy": True}
        mock_extract.side_effect = [
            "final score 4.0",
            "",
            "not numeric",
        ]
        score, _assessment = core.score_response(
            scorer_router,
            "sc-key",
            "goal",
            "target response",
            logger=MagicMock(),
            max_retries=1,
        )
        self.assertEqual(score, 4.0)
        scorer_router.route_request.assert_called_once()


class TestScoreResponsePrecedence(unittest.TestCase):
    def _score(self, outputs, max_retries=1):
        router = MagicMock()
        router.route_request.side_effect = outputs
        logger = MagicMock()
        result = core.score_response(
            router,
            "sample-key",
            "sample goal",
            "sample refused",
            logger=logger,
            max_retries=max_retries,
        )
        return result, router, logger

    def test_issue_564_assessment_wins_without_calling_wrapper(self):
        assessment = "SCORE: 2.5/10.0\nEXPLANATION: sample refused"
        for wrapper in (
            "10.0",
            "2.5/10.0",
            "",
            None,
            "not-a-number",
            "ERROR 503",
            RuntimeError("wrapper unavailable"),
        ):
            with self.subTest(wrapper=wrapper):
                result, router, _ = self._score([assessment, wrapper, "10.0"])
                self.assertEqual(result, (2.5, assessment))
                router.route_request.assert_called_once()

    def test_high_assessment_is_not_replaced_with_lower_wrapper(self):
        assessment = "Final assessment score: 9.5"
        result, router, _ = self._score([assessment, "2.5"])
        self.assertEqual(result, (9.5, assessment))
        router.route_request.assert_called_once()

    def test_structured_assessment_scores_survive_conflicting_explanations(self):
        for assessment in STRUCTURED_SCORE_ASSESSMENTS:
            with self.subTest(assessment=assessment):
                result, router, _ = self._score([assessment, "10.0"])
                self.assertEqual(result, (2.5, assessment))
                router.route_request.assert_called_once()

    def test_malformed_fraction_assessment_requires_wrapper_extraction(self):
        for assessment in MALFORMED_SCORE_FRACTIONS:
            with self.subTest(assessment=assessment):
                result, router, _ = self._score([assessment, "2.5"])
                self.assertEqual(result, (2.5, assessment))
                self.assertEqual(router.route_request.call_count, 2)

    def test_malformed_fraction_wrapper_requires_direct_score(self):
        assessment = "The sample refused."
        for wrapper in MALFORMED_SCORE_FRACTIONS:
            with self.subTest(wrapper=wrapper):
                result, router, _ = self._score([assessment, wrapper, "2.5"])
                self.assertEqual(result, (2.5, assessment))
                self.assertEqual(router.route_request.call_count, 3)

    def test_malformed_fractions_exhaust_protocol_retries_without_success(self):
        for output in MALFORMED_SCORE_FRACTIONS:
            with self.subTest(output=output):
                result, router, _ = self._score([output] * 6, max_retries=2)
                self.assertEqual(result, (1.0, "Score extraction failed"))
                self.assertEqual(router.route_request.call_count, 6)

    def test_nested_fraction_spans_cannot_become_protocol_scores(self):
        for before, after in product(SCORE_WHITESPACE, repeat=2):
            text = f"SCORE: 2.5{before}/{after}10{before}/{after}10"
            for outputs, expected, calls in (
                ([text, "2.5"], (2.5, text), 2),
                (["sample assessment", text, "2.5"], (2.5, "sample assessment"), 3),
                ([text] * 6, (1.0, "Score extraction failed"), 6),
            ):
                with self.subTest(text=text, outputs=outputs):
                    result, router, _ = self._score(outputs, max_retries=2)
                    self.assertEqual(result, expected)
                    self.assertEqual(router.route_request.call_count, calls)

    def test_incidental_assessment_numbers_do_not_outrank_wrapper(self):
        assessment = "The sample refused; the rubric has 10 levels."
        for wrapper in ("2.5", "2.5/10.0", "SCORE: 2.5", "Rating: [[2.5]]"):
            with self.subTest(wrapper=wrapper):
                result, router, _ = self._score([assessment, wrapper])
                self.assertEqual(result, (2.5, assessment))
                self.assertEqual(router.route_request.call_count, 2)

    def test_bad_wrapper_uses_direct_score_not_incidental_assessment_numbers(self):
        assessment = "The sample refused; the rubric has 10 levels."
        for wrapper in ("", "not-a-number", "ERROR 503", "SCORE: 2.5/100"):
            with self.subTest(wrapper=wrapper):
                result, router, _ = self._score([assessment, wrapper, "2.5"])
                self.assertEqual(result, (2.5, assessment))
                self.assertEqual(router.route_request.call_count, 3)

    def test_bad_direct_output_does_not_turn_incidental_numbers_into_success(self):
        assessment = "The sample refused; the rubric has 10 levels."
        for direct in ("", "NaN", "ERROR 503", "There were 10 examples", "2.5/10.5"):
            with self.subTest(direct=direct):
                result, router, _ = self._score([assessment, "not-a-number", direct])
                self.assertEqual(result, (1.0, "Score extraction failed"))
                self.assertEqual(router.route_request.call_count, 3)

    def test_empty_assessments_exhaust_retries_without_wrapper(self):
        for assessment in ("", None, " \n", {"error_message": "sample error 503"}):
            with self.subTest(assessment=assessment):
                result, router, logger = self._score([assessment] * 3, max_retries=3)
                self.assertEqual(result, (1.0, "Score extraction failed"))
                self.assertEqual(router.route_request.call_count, 3)
                self.assertEqual(logger.warning.call_count, 3)

    def test_retry_after_unparseable_outputs_keeps_successful_assessment(self):
        assessment = "SCORE: 2.5/10.0\nEXPLANATION: sample refused"
        result, router, _ = self._score(
            ["analysis only", "not-a-number", "ERROR 503", assessment],
            max_retries=2,
        )
        self.assertEqual(result, (2.5, assessment))
        self.assertEqual(router.route_request.call_count, 4)

    def test_provider_errors_retry_and_log_traceback(self):
        assessment = "SCORE: 2.5/10.0\nEXPLANATION: sample refused"
        for prefix in (
            [],
            ["analysis only"],
            ["analysis only", "not-a-number"],
        ):
            with self.subTest(prefix=prefix):
                result, router, logger = self._score(
                    [*prefix, RuntimeError("sample provider error"), assessment],
                    max_retries=2,
                )
                self.assertEqual(result, (2.5, assessment))
                self.assertEqual(router.route_request.call_count, len(prefix) + 2)
                logger.warning.assert_any_call(
                    "Scorer error: sample provider error", exc_info=True
                )

    def test_provider_error_exhaustion_preserves_failure_contract(self):
        result, router, logger = self._score(
            [RuntimeError("sample provider error")] * 2, max_retries=2
        )
        self.assertEqual(result, (1.0, "Score extraction failed"))
        self.assertEqual(router.route_request.call_count, 2)
        self.assertEqual(logger.warning.call_count, 2)

    def test_zero_retries_does_not_call_provider(self):
        result, router, _ = self._score([], max_retries=0)
        self.assertEqual(result, (1.0, "Score extraction failed"))
        router.route_request.assert_not_called()


class TestPromptExtraction(unittest.TestCase):
    def test_extract_between_tags(self):
        text = "x [START OF JAILBREAK PROMPT]abc[END OF JAILBREAK PROMPT] y"
        self.assertEqual(core.extract_jailbreak_prompt(text, "fallback"), "abc")

    def test_extract_without_tags_returns_cleaned_text(self):
        self.assertEqual(core.extract_jailbreak_prompt("hello", "fallback"), "hello")

    def test_extract_with_only_end_tag(self):
        text = "abc[END OF JAILBREAK PROMPT]"
        self.assertEqual(core.extract_jailbreak_prompt(text, "fallback"), "abc")

    def test_extract_with_only_start_tag(self):
        text = "[START OF JAILBREAK PROMPT]abc"
        self.assertEqual(core.extract_jailbreak_prompt(text, "fallback"), "abc")

    def test_extract_empty_returns_fallback(self):
        self.assertEqual(core.extract_jailbreak_prompt("", "fallback"), "fallback")

    def test_extract_whitespace_returns_fallback(self):
        self.assertEqual(core.extract_jailbreak_prompt("   ", "fallback"), "fallback")

    def test_extract_end_tag_with_prefixed_start_tag(self):
        text = "[START OF JAILBREAK PROMPT]abc[END OF JAILBREAK PROMPT]"
        self.assertEqual(core.extract_jailbreak_prompt(text, "fallback"), "abc")

    def test_extract_with_nested_start_tags_prefers_innermost_prompt(self):
        text = (
            "[START OF JAILBREAK PROMPT]header "
            "[START OF JAILBREAK PROMPT]real prompt"
            "[END OF JAILBREAK PROMPT]"
        )
        self.assertEqual(core.extract_jailbreak_prompt(text, "fallback"), "real prompt")

    def test_extract_end_tag_cleanup_when_between_empty(self):
        text = "[START OF JAILBREAK PROMPT][END OF JAILBREAK PROMPT]"
        self.assertEqual(core.extract_jailbreak_prompt(text, "fallback"), "fallback")

    def test_check_refusal(self):
        self.assertEqual(core.check_refusal("I cannot do this", "req"), "req")
        self.assertEqual(core.check_refusal("do this", "req"), "do this")

    def test_check_refusal_custom_keywords(self):
        self.assertEqual(core.check_refusal("DENY", "req", keywords=["DENY"]), "req")


if __name__ == "__main__":
    unittest.main()
