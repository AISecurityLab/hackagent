import unittest
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.autodan_turbo import summarizer


class TestSummarizerHelpers(unittest.TestCase):
    def test_truncate_for_log(self):
        self.assertEqual(summarizer._truncate_for_log(None), "")
        self.assertEqual(summarizer._truncate_for_log("abc", limit=5), "abc")
        self.assertTrue(summarizer._truncate_for_log("x" * 20, limit=5).endswith("..."))

    def test_extract_json_dict_plain_json(self):
        obj = summarizer._extract_json_dict('{"Strategy":"S","Definition":"D"}')
        self.assertEqual(obj["Strategy"], "S")

    def test_extract_json_dict_substring(self):
        obj = summarizer._extract_json_dict(
            'noise {"Strategy":"S","Definition":"D"} tail'
        )
        self.assertEqual(obj["Definition"], "D")

    def test_extract_json_dict_regex_fallback(self):
        obj = summarizer._extract_json_dict('"Strategy": "S1" and "Definition": "D1"')
        self.assertEqual(obj, {"Strategy": "S1", "Definition": "D1"})

    def test_extract_json_dict_second_parse_exception_path(self):
        text = '{invalid json} "Strategy": "S2" "Definition": "D2"'
        obj = summarizer._extract_json_dict(text)
        self.assertEqual(obj, {"Strategy": "S2", "Definition": "D2"})


class TestSummarizeStrategy(unittest.TestCase):
    @patch(
        "hackagent.attacks.techniques.autodan_turbo.summarizer.extract_response_content"
    )
    def test_summarize_strategy_success(self, mock_extract):
        router = MagicMock()
        router.route_request.return_value = {"dummy": True}
        mock_extract.side_effect = [
            "analysis with strategy",
            '{"Strategy":"Storytelling","Definition":"Uses narrative framing."}',
        ]

        result = summarizer.summarize_strategy(
            router=router,
            key="sum-key",
            request="goal",
            weak_prompt="weak",
            strong_prompt="strong",
            library={},
            logger=MagicMock(),
            max_retries=1,
        )

        self.assertIsInstance(result, dict)
        self.assertEqual(result["Strategy"], "Storytelling")
        self.assertEqual(router.route_request.call_count, 2)

    @patch(
        "hackagent.attacks.techniques.autodan_turbo.summarizer.extract_response_content"
    )
    def test_summarize_strategy_returns_none_when_unparseable(self, mock_extract):
        router = MagicMock()
        router.route_request.return_value = {"dummy": True}
        mock_extract.side_effect = [
            "analysis text",
            "not json and no fields",
        ]
        result = summarizer.summarize_strategy(
            router=router,
            key="sum-key",
            request="goal",
            weak_prompt="weak",
            strong_prompt="strong",
            library={},
            logger=MagicMock(),
            max_retries=1,
        )
        self.assertIsNone(result)

    @patch(
        "hackagent.attacks.techniques.autodan_turbo.summarizer.extract_response_content"
    )
    def test_summarize_strategy_handles_exception_and_retries(self, mock_extract):
        router = MagicMock()
        router.route_request.side_effect = RuntimeError("boom")
        mock_extract.return_value = None
        result = summarizer.summarize_strategy(
            router=router,
            key="sum-key",
            request="goal",
            weak_prompt="weak",
            strong_prompt="strong",
            library={},
            logger=MagicMock(),
            max_retries=2,
        )
        self.assertIsNone(result)
        self.assertEqual(router.route_request.call_count, 2)

    @patch(
        "hackagent.attacks.techniques.autodan_turbo.summarizer.extract_response_content"
    )
    def test_summarize_strategy_analysis_empty_path(self, mock_extract):
        router = MagicMock()
        router.route_request.return_value = {"dummy": True}
        mock_extract.return_value = None
        result = summarizer.summarize_strategy(
            router=router,
            key="sum-key",
            request="goal",
            weak_prompt="weak",
            strong_prompt="strong",
            library={},
            logger=MagicMock(),
            max_retries=1,
        )
        self.assertIsNone(result)

    @patch(
        "hackagent.attacks.techniques.autodan_turbo.summarizer.extract_response_content"
    )
    def test_summarize_strategy_wrapper_empty_path(self, mock_extract):
        router = MagicMock()
        router.route_request.return_value = {"dummy": True}
        mock_extract.side_effect = ["analysis", None]
        result = summarizer.summarize_strategy(
            router=router,
            key="sum-key",
            request="goal",
            weak_prompt="weak",
            strong_prompt="strong",
            library={},
            logger=MagicMock(),
            max_retries=1,
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
