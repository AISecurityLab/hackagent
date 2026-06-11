# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the shared inline judge runner (PAP / BoN generation loops).

``InlineStepJudge`` builds judge evaluators from raw config and scores a single
candidate response. These tests cover config-defaults, the init-time filtering
of invalid judge configs, and the ``is_jailbreak`` scoring path (column mapping,
same-type suffixing, best-score aggregation, and per-judge error isolation) by
injecting fake evaluators so no real model is called.
"""

import logging
import unittest
from unittest.mock import MagicMock, patch

from hackagent.attacks.evaluator.inline_step_judge import (
    InlineStepJudge,
    build_inline_judge_base_config,
)


class _FakeEvaluator:
    """Minimal evaluator: returns the configured row(s) from ``evaluate``."""

    def __init__(self, rows=None, raises=False):
        self._rows = rows if rows is not None else []
        self._raises = raises

    def evaluate(self, _input):
        if self._raises:
            raise RuntimeError("judge exploded")
        return self._rows


def _judge(**kw):
    judge = InlineStepJudge.__new__(InlineStepJudge)
    judge.logger = logging.getLogger("test")
    judge._judges = kw.get("judges", [])
    return judge


class TestBuildBaseConfig(unittest.TestCase):
    def test_defaults_when_empty(self):
        cfg = build_inline_judge_base_config({})
        self.assertEqual(cfg["batch_size"], 1)
        self.assertEqual(cfg["max_tokens_eval"], 256)
        self.assertEqual(cfg["temperature"], 0.0)
        self.assertIsNone(cfg["organization_id"])

    def test_overrides_are_read(self):
        cfg = build_inline_judge_base_config(
            {"batch_size_judge": 4, "judge_timeout": 30, "organization_id": "org-1"}
        )
        self.assertEqual(cfg["batch_size"], 4)
        self.assertEqual(cfg["timeout"], 30)
        self.assertEqual(cfg["organization_id"], "org-1")


class TestInit(unittest.TestCase):
    def test_invalid_judge_configs_yield_no_judges(self):
        judge = InlineStepJudge(
            judges_config=[
                {"type": "unknown_type", "identifier": "x"},  # bad type
                {"type": "jailbreakbench"},  # missing identifier
            ],
            base_eval_config={},
            client=MagicMock(),
            logger=logging.getLogger("test"),
        )
        self.assertFalse(judge.available)
        self.assertEqual(judge.judge_count, 0)

    def test_valid_judge_is_constructed(self):
        captured = {}

        class _FakeEvaluatorClass:
            def __init__(self, client, config, run_id, tracking_client, tracker):
                captured["config"] = config
                captured["run_id"] = run_id

        with patch.dict(
            "hackagent.attacks.evaluator.inline_step_judge.EVALUATOR_MAP",
            {"jailbreakbench": _FakeEvaluatorClass},
            clear=False,
        ):
            judge = InlineStepJudge(
                judges_config=[
                    {
                        "type": "jailbreakbench",
                        "identifier": "org/JailbreakBench",
                        "api_key": "secret",
                        "endpoint": "https://judge.example/api",
                    }
                ],
                base_eval_config=build_inline_judge_base_config({}),
                client=MagicMock(),
                logger=logging.getLogger("test"),
                run_id="run-9",
            )
        self.assertTrue(judge.available)
        self.assertEqual(judge.judge_count, 1)
        self.assertEqual(captured["run_id"], "run-9")
        # The configured model id flowed into the evaluator config.
        self.assertEqual(captured["config"].model_id, "org/JailbreakBench")

    def test_evaluator_construction_failure_is_caught(self):
        class _BoomEvaluatorClass:
            def __init__(self, *a, **k):
                raise RuntimeError("init failed")

        with patch.dict(
            "hackagent.attacks.evaluator.inline_step_judge.EVALUATOR_MAP",
            {"jailbreakbench": _BoomEvaluatorClass},
            clear=False,
        ):
            judge = InlineStepJudge(
                judges_config=[
                    {"type": "jailbreakbench", "identifier": "org/JailbreakBench"}
                ],
                base_eval_config={},
                client=MagicMock(),
                logger=logging.getLogger("test"),
            )
        self.assertFalse(judge.available)


class TestIsJailbreak(unittest.TestCase):
    def test_no_judges_returns_failure(self):
        success, score, cols = _judge(judges=[]).is_jailbreak("g", "p", "r")
        self.assertFalse(success)
        self.assertEqual(score, 0.0)
        self.assertEqual(cols, {})

    def test_single_judge_maps_columns_and_scores(self):
        ev = _FakeEvaluator(rows=[{"eval_jb": 1.0, "explanation_jb": "leaked"}])
        judge = _judge(judges=[("jailbreakbench", ev)])
        success, score, cols = judge.is_jailbreak("goal", "prefix", "resp")
        self.assertTrue(success)
        self.assertEqual(score, 1.0)
        # No suffix when only one judge of this type.
        self.assertEqual(cols["eval_jb"], 1.0)
        self.assertEqual(cols["explanation_jb"], "leaked")

    def test_two_same_type_judges_get_suffixed_columns(self):
        ev1 = _FakeEvaluator(rows=[{"eval_jb": 0.0}])
        ev2 = _FakeEvaluator(rows=[{"eval_jb": 1.0}])
        judge = _judge(judges=[("jailbreakbench", ev1), ("jailbreakbench", ev2)])
        success, score, cols = judge.is_jailbreak("g", "p", "r")
        self.assertEqual(cols["eval_jb_1"], 0.0)
        self.assertEqual(cols["eval_jb_2"], 1.0)
        # best_score aggregates the max across both judges.
        self.assertEqual(score, 1.0)
        self.assertTrue(success)

    def test_empty_evaluation_result_is_skipped(self):
        judge = _judge(judges=[("jailbreakbench", _FakeEvaluator(rows=[]))])
        success, score, _cols = judge.is_jailbreak("g", "p", "r")
        self.assertFalse(success)
        self.assertEqual(score, 0.0)

    def test_judge_exception_is_isolated(self):
        good = _FakeEvaluator(rows=[{"eval_jb": 1.0}])
        bad = _FakeEvaluator(raises=True)
        judge = _judge(judges=[("harmbench", bad), ("jailbreakbench", good)])
        success, score, cols = judge.is_jailbreak("g", "p", "r")
        # The good judge still contributes despite the bad one throwing.
        self.assertTrue(success)
        self.assertEqual(score, 1.0)
        self.assertIn("eval_jb", cols)

    def test_non_numeric_score_does_not_crash(self):
        ev = _FakeEvaluator(rows=[{"eval_jb": "not-a-number"}])
        judge = _judge(judges=[("jailbreakbench", ev)])
        success, score, _cols = judge.is_jailbreak("g", "p", "r")
        self.assertFalse(success)
        self.assertEqual(score, 0.0)


if __name__ == "__main__":
    unittest.main()
