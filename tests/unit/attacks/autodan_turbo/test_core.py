import unittest
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.autodan_turbo import core


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
        cfg = {"max_new_tokens": 10, "temperature": 0.1}
        out = core.query_target(agent_router, "v-key", "prompt", cfg, MagicMock())
        self.assertEqual(out, "target out")

    @patch("hackagent.attacks.techniques.autodan_turbo.core.extract_response_content")
    def test_score_response_wrapper_parsed(self, mock_extract):
        scorer_router = MagicMock()
        scorer_router.route_request.return_value = {"dummy": True}
        mock_extract.side_effect = [
            "Analysis ... final score 8.0",
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

    @patch("hackagent.attacks.techniques.autodan_turbo.core.extract_response_content")
    def test_score_response_wrapper_unparseable_falls_back_assessment(
        self, mock_extract
    ):
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
    def test_score_response_assessment_fallback_after_direct_numeric_fail(
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

    def test_extract_end_tag_cleanup_when_between_empty(self):
        text = "[START OF JAILBREAK PROMPT][END OF JAILBREAK PROMPT]"
        self.assertEqual(
            core.extract_jailbreak_prompt(text, "fallback"), "[END OF JAILBREAK PROMPT]"
        )

    def test_check_refusal(self):
        self.assertEqual(core.check_refusal("I cannot do this", "req"), "req")
        self.assertEqual(core.check_refusal("do this", "req"), "do this")

    def test_check_refusal_custom_keywords(self):
        self.assertEqual(core.check_refusal("DENY", "req", keywords=["DENY"]), "req")


if __name__ == "__main__":
    unittest.main()
