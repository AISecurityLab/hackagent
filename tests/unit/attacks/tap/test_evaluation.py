# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for TAP evaluation helpers.

The actual judge calls live in ``BaseEvaluationStep._run_evaluation``; these
tests stub that out and focus on TAP's own logic: on-topic defaulting, score
extraction, judge-type inference, binary-score normalisation, judge-config
resolution, and the ``execute`` pipeline (scoring + tracker tracing).
"""

import logging
import unittest
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.tap.tap_evaluation import (
    TapEvaluation,
    _resolve_judges_config,
    execute,
)

logging.disable(logging.CRITICAL)


def _ev(config=None):
    e = TapEvaluation(config=config or {}, logger=MagicMock(), client=MagicMock())
    # Stub the inherited evaluation machinery so no model is called.
    e._build_base_eval_config = MagicMock(return_value={})
    e._run_evaluation = MagicMock(side_effect=lambda rows, judges, base: rows)
    e._enrich_items_with_scores = MagicMock()
    return e


class TestOnTopic(unittest.TestCase):
    def test_skipped_when_no_judges(self):
        e = _ev()
        rows = e.evaluate_on_topic([{"goal": "g"}], on_topic_judges=None)
        self.assertEqual(rows[0]["eval_on_topic"], 1)
        self.assertIn("skipped", rows[0]["explanation_on_topic"])
        e._run_evaluation.assert_not_called()

    def test_runs_evaluation_when_judges_present(self):
        e = _ev()
        e.evaluate_on_topic([{"goal": "g"}], on_topic_judges=[{"type": "on_topic"}])
        e._run_evaluation.assert_called_once()

    def test_score_on_topic_extracts_scores(self):
        e = _ev()
        scores = e.score_on_topic("goal", ["p1", "p2"], on_topic_judges=None)
        self.assertEqual(scores, [1, 1])


class TestExtractScores(unittest.TestCase):
    def test_numeric_none_and_unparseable(self):
        rows = [{"best_score": 9}, {"best_score": None}, {"best_score": "oops"}]
        self.assertEqual(
            TapEvaluation.extract_scores(rows, "best_score", default=-1),
            [9, -1, -1],
        )

    def test_float_strings_are_truncated_to_int(self):
        self.assertEqual(TapEvaluation.extract_scores([{"s": "7.9"}], "s"), [7])


class TestJudgeTypeInference(unittest.TestCase):
    def test_explicit_type_wins(self):
        self.assertEqual(
            TapEvaluation._infer_judge_type({"type": "Nuanced"}), "nuanced"
        )

    def test_evaluator_type_fallback(self):
        self.assertEqual(
            TapEvaluation._infer_judge_type({"evaluator_type": "harmbench"}),
            "harmbench",
        )

    def test_inferred_from_identifier(self):
        # Shared inference treats HarmClassifier/HarmBenchVariant as harmbench_variant.
        self.assertEqual(
            TapEvaluation._infer_judge_type({"identifier": "x/HarmClassifier"}),
            "harmbench_variant",
        )
        self.assertEqual(
            TapEvaluation._infer_judge_type({"identifier": "x/HarmBenchVariant"}),
            "harmbench_variant",
        )
        self.assertEqual(
            TapEvaluation._infer_judge_type({"identifier": "x/HarmBench-7B"}),
            "harmbench",
        )
        self.assertEqual(
            TapEvaluation._infer_judge_type({"identifier": "jailbreak-judge"}),
            "jailbreakbench",
        )
        self.assertEqual(
            TapEvaluation._infer_judge_type({"identifier": "nuanced-x"}), "nuanced"
        )

    def test_unknown_returns_empty(self):
        self.assertEqual(TapEvaluation._infer_judge_type({"identifier": "mystery"}), "")

    def test_judges_are_binary(self):
        self.assertFalse(TapEvaluation._judges_are_binary([]))
        self.assertTrue(TapEvaluation._judges_are_binary([{"type": "harmbench"}]))
        # scorer with explicit decimal range is NOT binary
        self.assertFalse(
            TapEvaluation._judges_are_binary([{"type": "scorer", "range": "decimal"}])
        )
        # mixing binary and decimal is NOT all-binary
        self.assertFalse(
            TapEvaluation._judges_are_binary(
                [{"type": "harmbench"}, {"type": "scorer", "range": "decimal"}]
            )
        )


class TestScoreCandidates(unittest.TestCase):
    def test_binary_scores_normalised_to_1_10(self):
        e = _ev()
        # evaluate_judge returns rows whose best_score is 0/1 (binary judge).
        e.evaluate_judge = MagicMock(
            return_value=[{"best_score": 1}, {"best_score": 0}]
        )
        scores = e.score_candidates(
            "goal", ["p1", "p2"], ["r1", "r2"], [{"type": "harmbench"}]
        )
        self.assertEqual(scores, [10, 1])

    def test_non_binary_scores_passed_through(self):
        e = _ev()
        e.evaluate_judge = MagicMock(
            return_value=[{"best_score": 7}, {"best_score": 3}]
        )
        scores = e.score_candidates(
            "goal", ["p1", "p2"], ["r1", "r2"], [{"type": "scorer", "range": "decimal"}]
        )
        self.assertEqual(scores, [7, 3])

    def test_evaluate_judge_enriches_scores(self):
        e = _ev()
        e.evaluate_judge([{"goal": "g"}], [{"type": "nuanced"}])
        e._enrich_items_with_scores.assert_called_once()


class TestResolveJudgesConfig(unittest.TestCase):
    def test_list_form(self):
        self.assertEqual(_resolve_judges_config({"judges": [{"a": 1}]}), [{"a": 1}])

    def test_single_judge_dict(self):
        self.assertEqual(_resolve_judges_config({"judge": {"a": 1}}), [{"a": 1}])

    def test_empty(self):
        self.assertEqual(_resolve_judges_config({}), [])
        self.assertEqual(_resolve_judges_config({"judges": []}), [])


class TestExecutePipeline(unittest.TestCase):
    def test_empty_input(self):
        self.assertEqual(execute([], {}, MagicMock(), MagicMock()), [])

    def test_precomputed_score_skips_judging(self):
        # best_score already present → no scoring call, but tracker still traces.
        tracker = MagicMock()
        tracker.get_goal_context.return_value = object()
        config = {"_tracker": tracker, "judges": [{"type": "nuanced"}]}
        data = [{"goal": "g", "best_score": 8, "is_success": True}]
        with patch.object(TapEvaluation, "score_candidates") as mock_score:
            out = execute(data, config, MagicMock(), MagicMock())
        mock_score.assert_not_called()
        tracker.add_evaluation_trace.assert_called_once()
        self.assertEqual(out[0]["best_score"], 8)

    def test_missing_score_triggers_judging(self):
        config = {
            "judges": [{"type": "nuanced"}],
            "tap_params": {"success_score_threshold": 7},
        }
        data = [{"goal": "g", "best_prompt": "p", "best_response": "r"}]
        with patch.object(
            TapEvaluation, "score_candidates", return_value=[9]
        ) as mock_score:
            out = execute(data, config, MagicMock(), MagicMock())
        mock_score.assert_called_once()
        self.assertEqual(out[0]["best_score"], 9)
        self.assertTrue(out[0]["is_success"])  # 9 >= threshold 7

    def test_no_tracker_no_trace(self):
        config = {"judges": [{"type": "nuanced"}]}
        data = [{"goal": "g", "best_score": 5}]
        # Should not raise despite no _tracker in config.
        out = execute(data, config, MagicMock(), MagicMock())
        self.assertEqual(out[0]["best_score"], 5)


if __name__ == "__main__":
    unittest.main()
