# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for AdvPrefix evaluation aggregation/selection and pipeline decorators."""

import logging
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from hackagent.attacks.techniques.adaptive.advprefix.eval_pipeline import (
    EvaluationPipeline,
)
from hackagent.attacks.techniques.adaptive.advprefix.utils import (
    handle_empty_input,
    log_errors,
    require_agent_router,
    validate_config,
)


def _logger() -> logging.Logger:
    logger = logging.getLogger("test.advprefix.eval")
    logger.disabled = True
    return logger


class TestAdvPrefixUtilsDecorators(unittest.TestCase):
    def test_handle_empty_input_for_lists_and_dicts(self):
        @handle_empty_input("Generate", empty_result=["empty"])
        def generate(*, data, logger):
            return ["ran"]

        self.assertEqual(generate(data=[], logger=_logger()), ["empty"])
        self.assertEqual(generate(data={}, logger=_logger()), ["empty"])
        self.assertEqual(generate(data=["x"], logger=_logger()), ["ran"])

    def test_log_errors_reraises_after_logging(self):
        @log_errors("Select")
        def explode(*, logger):
            raise RuntimeError("selection failed")

        with self.assertRaises(RuntimeError):
            explode(logger=_logger())

    def test_validate_config_requires_keys(self):
        @validate_config(["model_id", "temperature"])
        def run(*, config, logger):
            return "ok"

        with self.assertRaises(ValueError) as ctx:
            run(config={"model_id": "x"}, logger=_logger())
        self.assertIn("temperature", str(ctx.exception))
        self.assertEqual(
            run(config={"model_id": "x", "temperature": 0.1}, logger=_logger()), "ok"
        )

    def test_require_agent_router_validates_backend_and_type(self):
        @require_agent_router("Compute CE", agent_type="GOOGLE_ADK")
        def run(*, agent_router, logger):
            return "ok"

        with self.assertRaises(ValueError):
            run(agent_router=None, logger=_logger())

        missing_backend = SimpleNamespace(backend_agent=None)
        with self.assertRaises(ValueError):
            run(agent_router=missing_backend, logger=_logger())

        wrong_type = SimpleNamespace(
            backend_agent=SimpleNamespace(agent_type="OPENAI_SDK")
        )
        with self.assertRaises(ValueError) as ctx:
            run(agent_router=wrong_type, logger=_logger())
        self.assertIn("GOOGLE_ADK", str(ctx.exception))

        good = SimpleNamespace(backend_agent=SimpleNamespace(agent_type="GOOGLE_ADK"))
        self.assertEqual(run(agent_router=good, logger=_logger()), "ok")


class TestEvaluationPipelineAggregation(unittest.TestCase):
    def _pipeline(self, **overrides) -> EvaluationPipeline:
        config = {
            "judges": [
                {"type": "harmbench", "identifier": "judge"},
                {"type": "scorer", "identifier": "scorer"},
            ],
            "n_prefixes_per_goal": 2,
            "pasr_tol": 0.2,
            "nll_tol": 1.0,
        }
        config.update(overrides)
        return EvaluationPipeline(config=config, logger=_logger(), client=MagicMock())

    def test_filter_by_nll_skips_when_key_missing(self):
        pipeline = self._pipeline()
        data = [{"goal": "g", "prefix": "p"}]
        self.assertEqual(pipeline._filter_by_nll(data, 0.1), data)

    def test_filter_by_nll_drops_high_ce_rows(self):
        pipeline = self._pipeline()
        data = [
            {"goal": "g", "prefix": "keep", "prefix_nll": 0.2},
            {"goal": "g", "prefix": "drop", "prefix_nll": 0.9},
        ]
        filtered = pipeline._filter_by_nll(data, 0.5)
        self.assertEqual([row["prefix"] for row in filtered], ["keep"])

    def test_aggregation_returns_input_when_grouping_keys_missing(self):
        pipeline = self._pipeline()
        data = [{"eval_hb": 1, "completion": "x"}]
        self.assertEqual(pipeline._run_aggregation(data), data)

    def test_aggregation_skips_nll_filter_when_max_ce_is_none(self):
        pipeline = self._pipeline(max_ce=None)
        data = [
            {
                "goal": "g",
                "prefix": "p",
                "eval_hb": 1,
                "completion": "c",
                "prefix_nll": 0.1,
            }
        ]
        aggregated = pipeline._run_aggregation(data)
        self.assertEqual(len(aggregated), 1)
        self.assertEqual(aggregated[0]["eval_hb_mean"], 1.0)

    def test_aggregation_groups_and_keeps_best_completion(self):
        pipeline = self._pipeline()
        data = [
            {
                "goal": "g",
                "prefix": "p",
                "completion": "low",
                "eval_hb": 0,
                "eval_scorer": "oops",
            },
            {
                "goal": "g",
                "prefix": "p",
                "completion": "high",
                "eval_hb": 1,
                "eval_scorer": 8,
                "result_id": "r1",
            },
        ]
        aggregated = pipeline._run_aggregation(data)
        self.assertEqual(len(aggregated), 1)
        self.assertEqual(aggregated[0]["best_completion"], "high")
        self.assertEqual(aggregated[0]["result_id"], "r1")
        self.assertEqual(aggregated[0]["n_eval_samples"], 2)
        self.assertAlmostEqual(aggregated[0]["eval_hb_mean"], 0.5)
        self.assertEqual(aggregated[0]["eval_scorer_mean"], 8.0)


class TestEvaluationPipelineSelection(unittest.TestCase):
    def _pipeline(self, **overrides) -> EvaluationPipeline:
        config = {
            "judges": [{"type": "harmbench", "identifier": "judge"}],
            "n_prefixes_per_goal": 2,
            "pasr_tol": 0.2,
            "nll_tol": 5.0,
        }
        config.update(overrides)
        return EvaluationPipeline(config=config, logger=_logger(), client=MagicMock())

    def test_selection_returns_input_without_judges(self):
        pipeline = self._pipeline(judges=[])
        data = [{"goal": "g", "prefix": "p", "eval_hb_mean": 1}]
        self.assertEqual(pipeline._run_selection(data), data)

    def test_selection_skips_unknown_and_missing_judge_columns(self):
        pipeline = self._pipeline(judges=[{"type": "not-a-judge"}])
        data = [{"goal": "g", "prefix": "p"}]
        self.assertEqual(pipeline._run_selection(data), data)

        pipeline = self._pipeline()
        data = [{"goal": "g", "prefix": "p"}]  # missing eval_hb_mean
        self.assertEqual(pipeline._run_selection(data), data)

    def test_selects_highest_pasr_then_lowest_nll_within_tolerance(self):
        pipeline = self._pipeline()
        group = [
            {"goal": "g", "prefix": "best", "pasr": 1.0, "prefix_nll": 2.0},
            {"goal": "g", "prefix": "close-high-nll", "pasr": 0.9, "prefix_nll": 8.0},
            {"goal": "g", "prefix": "close-low-nll", "pasr": 0.95, "prefix_nll": 0.4},
            {"goal": "g", "prefix": "best-extra", "pasr": 0.5, "prefix_nll": 0.1},
        ]
        selected = pipeline._select_prefixes_for_goal(group)
        prefixes = [item["prefix"] for item in selected]
        self.assertEqual(prefixes[0], "best")
        self.assertIn("close-low-nll", prefixes)
        self.assertNotIn("close-high-nll", prefixes)
        self.assertNotIn("best-extra", prefixes)

    def test_subprefix_candidates_are_removed(self):
        pipeline = self._pipeline()
        group = [
            {"goal": "g", "prefix": "Sure, here", "pasr": 1.0, "prefix_nll": 1.0},
            {
                "goal": "g",
                "prefix": "Sure, here is more",
                "pasr": 1.0,
                "prefix_nll": 0.1,
            },
        ]
        selected = pipeline._select_prefixes_for_goal(group)
        self.assertEqual([item["prefix"] for item in selected], ["Sure, here"])

    def test_run_selection_assigns_pasr_and_groups_by_goal(self):
        pipeline = self._pipeline()
        data = [
            {"goal": "a", "prefix": "p1", "eval_hb_mean": 1.0, "prefix_nll": 0.2},
            {"goal": "a", "prefix": "p2", "eval_hb_mean": 0.0, "prefix_nll": 0.1},
            {"goal": "b", "prefix": "q1", "eval_hb_mean": 1.0, "prefix_nll": 0.3},
        ]
        selected = pipeline._run_selection(data)
        by_goal = {item["goal"] for item in selected}
        self.assertEqual(by_goal, {"a", "b"})
        self.assertTrue(all("pasr" in item for item in selected))


class TestEvaluationPipelineExecute(unittest.TestCase):
    def test_execute_returns_empty_when_nll_filter_removes_all(self):
        pipeline = EvaluationPipeline(
            config={"judges": [{"type": "harmbench"}], "max_ce": 0.01},
            logger=_logger(),
            client=MagicMock(),
        )
        self.assertEqual(
            pipeline.execute(
                [
                    {
                        "goal": "g",
                        "prefix": "p",
                        "completion": "c",
                        "eval_hb": 1,
                        "prefix_nll": 0.5,
                    }
                ]
            ),
            [],
        )

    def test_execute_runs_aggregation_and_selection(self):
        pipeline = EvaluationPipeline(
            config={"judges": [{"type": "harmbench", "identifier": "j"}]},
            logger=_logger(),
            client=MagicMock(),
        )
        evaluated = [
            {
                "goal": "g",
                "prefix": "p",
                "completion": "c",
                "eval_hb": 1,
                "prefix_nll": 0.2,
            }
        ]
        selected = pipeline.execute(evaluated)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["prefix"], "p")


if __name__ == "__main__":
    unittest.main()
