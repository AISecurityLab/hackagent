# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the Best-of-N search loop and tracing."""

import logging
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.bon import generation as bongen
from hackagent.attacks.techniques.bon.generation import (
    _persist_step_trace,
    _search_single_goal,
    execute,
)

LOGGER = logging.getLogger("test.bon.generation")
LOGGER.addHandler(logging.NullHandler())


def _victim_router(response=None, side_effect=None):
    router = MagicMock()
    router.backend_agent = SimpleNamespace(id="victim-id")
    if side_effect is not None:
        router.route_request.side_effect = side_effect
    else:
        router.route_request.return_value = response or {"generated_text": "answer"}
    return router


def _judge(verdicts):
    """Inline judge stub returning the given (is_jailbreak, score, cols) tuples."""
    judge = MagicMock()
    judge.available = True
    judge.judge_count = 1
    judge.is_jailbreak.side_effect = list(verdicts)
    return judge


def _search(**overrides):
    kwargs = {
        "goal": "the goal",
        "goal_idx": 0,
        "n_steps": 1,
        "num_concurrent_k": 1,
        "target_max_tokens": None,
        "sigma": 0.4,
        "word_scrambling": False,
        "random_capitalization": False,
        "ascii_perturbation": False,
        "candidate_workers": 1,
        "victim_key": "victim-id",
        "agent_router": _victim_router(),
        "tracker": None,
        "step_judge": None,
        "logger": LOGGER,
    }
    kwargs.update(overrides)
    return _search_single_goal(**kwargs)


class TestSearchSingleGoal(unittest.TestCase):
    def test_single_step_returns_the_target_response(self):
        router = _victim_router({"generated_text": "the answer"})

        result = _search(agent_router=router)

        self.assertEqual(result["goal"], "the goal")
        self.assertEqual(result["response"], "the answer")
        self.assertEqual(result["step"], 0)
        self.assertEqual(result["candidate"], 0)
        self.assertFalse(result["success"])
        self.assertEqual(result["augmentation_params"]["sigma"], 0.4)

    def test_max_tokens_is_forwarded_when_configured(self):
        router = _victim_router()

        _search(agent_router=router, target_max_tokens=64)

        self.assertEqual(
            router.route_request.call_args.kwargs["request_data"]["max_tokens"], 64
        )

    def test_max_tokens_is_omitted_when_unset(self):
        router = _victim_router()

        _search(agent_router=router)

        self.assertNotIn(
            "max_tokens", router.route_request.call_args.kwargs["request_data"]
        )

    def test_judge_confirmation_stops_the_search_early(self):
        router = _victim_router()
        judge = _judge([(True, 1.0, {"eval_hb": 1})])

        result = _search(
            agent_router=router, n_steps=5, step_judge=judge, num_concurrent_k=1
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["best_score"], 1.0)
        self.assertEqual(result["eval_hb"], 1)
        self.assertEqual(router.route_request.call_count, 1)

    def test_search_continues_through_every_step_without_a_jailbreak(self):
        router = _victim_router()
        judge = _judge([(False, 0.0, {}), (False, 0.0, {}), (False, 0.0, {})])

        result = _search(agent_router=router, n_steps=3, step_judge=judge)

        self.assertFalse(result["success"])
        self.assertEqual(router.route_request.call_count, 3)

    def test_higher_scoring_step_replaces_the_previous_best(self):
        router = _victim_router()
        judge = _judge([(False, 0.2, {}), (False, 0.8, {"eval_scorer": 8})])

        result = _search(agent_router=router, n_steps=2, step_judge=judge)

        self.assertEqual(result["best_score"], 0.8)
        self.assertEqual(result["eval_scorer"], 8)
        self.assertEqual(result["step"], 1)

    def test_steps_without_a_response_are_skipped(self):
        router = _victim_router({"error_message": "timeout"})

        result = _search(agent_router=router, n_steps=2)

        self.assertIsNone(result["response"])
        self.assertIsNone(result["step"])
        self.assertEqual(router.route_request.call_count, 2)

    def test_request_exceptions_are_captured_per_candidate(self):
        router = _victim_router(side_effect=RuntimeError("connection reset"))

        result = _search(agent_router=router)

        self.assertIsNone(result["response"])
        self.assertFalse(result["success"])

    def test_guardrail_blocks_are_not_treated_as_errors(self):
        router = _victim_router(
            {
                "adapter_type": "guardrail",
                "generated_text": "Blocked by guardrail",
                "agent_specific_data": {"side": "input"},
            }
        )
        tracker = MagicMock()
        tracker.get_goal_context.return_value = SimpleNamespace(result_id="r")

        _search(agent_router=router, tracker=tracker)

        trace = tracker.add_interaction_trace.call_args_list[0].kwargs
        self.assertEqual(trace["response"]["adapter_type"], "guardrail")

    def test_longest_response_wins_within_a_step(self):
        responses = [{"generated_text": "short"}, {"generated_text": "much longer one"}]
        router = _victim_router(side_effect=responses)

        result = _search(agent_router=router, num_concurrent_k=2, candidate_workers=1)

        self.assertEqual(result["response"], "much longer one")

    def test_candidate_seeds_are_derived_from_the_step_index(self):
        router = _victim_router()

        result = _search(agent_router=router, n_steps=2, num_concurrent_k=2)

        # Final best comes from a later step, so the seed is >= num_concurrent_k.
        self.assertIsNotNone(result["seed"])

    def test_tracker_receives_step_traces(self):
        router = _victim_router()
        tracker = MagicMock()
        tracker.get_goal_context.return_value = SimpleNamespace(result_id="r")

        _search(agent_router=router, tracker=tracker, num_concurrent_k=2)

        step_names = [
            call.kwargs["step_name"]
            for call in tracker.add_interaction_trace.call_args_list
        ]
        self.assertEqual(step_names.count("BoN Step 1/1"), 2)
        self.assertIn("Evaluation – Step 1/1", step_names)

    def test_no_trace_is_written_without_a_goal_context(self):
        router = _victim_router()
        tracker = MagicMock()
        tracker.get_goal_context.return_value = None

        _search(agent_router=router, tracker=tracker)

        tracker.add_interaction_trace.assert_not_called()

    def test_failed_steps_still_produce_a_trace(self):
        router = _victim_router({"error_message": "timeout"})
        tracker = MagicMock()
        tracker.get_goal_context.return_value = SimpleNamespace(result_id="r")

        _search(agent_router=router, tracker=tracker)

        names = [
            call.kwargs["step_name"]
            for call in tracker.add_interaction_trace.call_args_list
        ]
        self.assertIn("Evaluation – Step 1/1", names)


class TestPersistStepTrace(unittest.TestCase):
    def _candidates(self):
        return {
            0: {
                "augmented_prompt": "prompt zero",
                "response": "response zero",
                "error": None,
                "guardrail_info": None,
                "candidate": 0,
                "seed": 0,
            },
            1: {
                "augmented_prompt": "prompt one",
                "response": None,
                "error": "timeout",
                "guardrail_info": None,
                "candidate": 1,
                "seed": 1,
            },
        }

    def test_each_candidate_gets_its_own_trace(self):
        tracker = MagicMock()
        candidates = self._candidates()

        _persist_step_trace(
            tracker=tracker,
            goal_ctx="ctx",
            step=0,
            n_steps=3,
            num_concurrent_k=2,
            sigma=0.4,
            candidate_results=candidates,
            step_best=candidates[0],
            judge_score=0.5,
            is_jailbreak=False,
            judge_cols={},
        )

        candidate_traces = [
            call.kwargs
            for call in tracker.add_interaction_trace.call_args_list
            if call.kwargs["step_name"] == "BoN Step 1/3"
        ]
        self.assertEqual(len(candidate_traces), 2)
        self.assertTrue(candidate_traces[0]["metadata"]["is_best"])
        self.assertFalse(candidate_traces[1]["metadata"]["is_best"])
        self.assertEqual(candidate_traces[0]["metadata"]["response_length"], 13)
        self.assertEqual(candidate_traces[1]["metadata"]["response_length"], 0)

    def test_missing_candidates_are_skipped(self):
        tracker = MagicMock()

        _persist_step_trace(
            tracker=tracker,
            goal_ctx="ctx",
            step=0,
            n_steps=1,
            num_concurrent_k=4,
            sigma=0.4,
            candidate_results={0: self._candidates()[0]},
            step_best=None,
            judge_score=0.0,
            is_jailbreak=False,
            judge_cols={},
        )

        candidate_traces = [
            call
            for call in tracker.add_interaction_trace.call_args_list
            if call.kwargs["step_name"] == "BoN Step 1/1"
        ]
        self.assertEqual(len(candidate_traces), 1)

    def test_evaluation_trace_summarises_the_verdict(self):
        tracker = MagicMock()
        candidates = self._candidates()

        _persist_step_trace(
            tracker=tracker,
            goal_ctx="ctx",
            step=1,
            n_steps=2,
            num_concurrent_k=2,
            sigma=0.4,
            candidate_results=candidates,
            step_best=candidates[0],
            judge_score=1.0,
            is_jailbreak=True,
            judge_cols={"eval_hb": 1, "explanation_hb": "model complied"},
        )

        evaluation = [
            call.kwargs
            for call in tracker.add_interaction_trace.call_args_list
            if call.kwargs["step_name"] == "Evaluation – Step 2/2"
        ][0]
        verdict = evaluation["response"]["generated_text"]
        self.assertIn("Best candidate: K1/2", verdict)
        self.assertIn("Jailbreak: YES", verdict)
        self.assertIn("Explanation: model complied", verdict)
        self.assertIn("response zero", verdict)
        self.assertTrue(evaluation["metadata"]["is_jailbreak"])

    def test_evaluation_trace_without_a_best_candidate(self):
        tracker = MagicMock()

        _persist_step_trace(
            tracker=tracker,
            goal_ctx="ctx",
            step=0,
            n_steps=1,
            num_concurrent_k=1,
            sigma=0.4,
            candidate_results={},
            step_best=None,
            judge_score=0.0,
            is_jailbreak=False,
            judge_cols={},
        )

        evaluation = tracker.add_interaction_trace.call_args.kwargs
        self.assertIn("Best candidate: N/A", evaluation["response"]["generated_text"])
        self.assertIsNone(evaluation["metadata"]["best_candidate_index"])

    def test_guardrail_candidates_are_rendered_as_guardrail_responses(self):
        tracker = MagicMock()
        candidates = {
            0: {
                "augmented_prompt": "p",
                "response": None,
                "error": None,
                "guardrail_info": {"side": "output"},
                "candidate": 0,
                "seed": 0,
            }
        }

        _persist_step_trace(
            tracker=tracker,
            goal_ctx="ctx",
            step=0,
            n_steps=1,
            num_concurrent_k=1,
            sigma=0.4,
            candidate_results=candidates,
            step_best=None,
            judge_score=0.0,
            is_jailbreak=False,
            judge_cols={},
        )

        candidate_trace = tracker.add_interaction_trace.call_args_list[0].kwargs
        self.assertEqual(candidate_trace["response"]["adapter_type"], "guardrail")
        self.assertEqual(
            candidate_trace["response"]["agent_specific_data"], {"side": "output"}
        )


class TestExecute(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(bongen, "_search_single_goal")
        self.search = patcher.start()
        self.addCleanup(patcher.stop)
        self.search.side_effect = lambda **kwargs: {
            "goal": kwargs["goal"],
            "response": "answer",
            "success": False,
            "best_score": 0.0,
        }

    def test_one_result_per_goal(self):
        results = execute(["g0", "g1"], _victim_router(), {}, LOGGER)

        self.assertEqual([r["goal"] for r in results], ["g0", "g1"])
        for row in results:
            self.assertIn("generation_elapsed_s", row)

    def test_bon_parameters_are_forwarded_to_the_search(self):
        execute(
            ["g"],
            _victim_router(),
            {
                "bon_params": {
                    "n_steps": 7,
                    "num_concurrent_k": 3,
                    "sigma": 0.9,
                    "word_scrambling": False,
                }
            },
            LOGGER,
        )

        kwargs = self.search.call_args.kwargs
        self.assertEqual(kwargs["n_steps"], 7)
        self.assertEqual(kwargs["num_concurrent_k"], 3)
        self.assertEqual(kwargs["sigma"], 0.9)
        self.assertFalse(kwargs["word_scrambling"])
        self.assertEqual(kwargs["candidate_workers"], 3)

    def test_inline_judge_is_created_when_ctx_judge_is_present(self):
        from hackagent.attacks._lib.inline_judge import CtxJudgeAdapter
        from tests.fakes.judge import FakeJudge

        port = FakeJudge(score=10.0, success=True)
        execute(
            ["g"],
            _victim_router(),
            {
                "judges": [{"identifier": "j"}],
                "_judge": port,
                "_backend": MagicMock(),
                "_run_id": "run-1",
            },
            LOGGER,
        )

        step_judge = self.search.call_args.kwargs["step_judge"]
        self.assertIsInstance(step_judge, CtxJudgeAdapter)
        self.assertTrue(step_judge.available)
        self.assertIs(step_judge._judge, port)

    def test_unavailable_judge_is_dropped(self):
        judge = MagicMock()
        judge.available = False

        with patch.object(bongen, "_StepJudge", return_value=judge):
            execute(
                ["g"],
                _victim_router(),
                {"judges": [{"identifier": "j"}], "_client": MagicMock()},
                LOGGER,
            )

        self.assertIsNone(self.search.call_args.kwargs["step_judge"])

    def test_no_judge_is_created_without_a_client(self):
        with patch.object(bongen, "_StepJudge") as judge_cls:
            execute(["g"], _victim_router(), {"judges": [{"identifier": "j"}]}, LOGGER)

        judge_cls.assert_not_called()
        self.assertIsNone(self.search.call_args.kwargs["step_judge"])

    def test_result_id_is_injected_from_the_tracker(self):
        tracker = MagicMock()
        tracker.get_goal_context.return_value = SimpleNamespace(result_id="res-9")

        results = execute(["g"], _victim_router(), {"_tracker": tracker}, LOGGER)

        self.assertEqual(results[0]["result_id"], "res-9")

    def test_missing_goal_context_leaves_the_row_without_a_result_id(self):
        tracker = MagicMock()
        tracker.get_goal_context.return_value = None

        results = execute(["g"], _victim_router(), {"_tracker": tracker}, LOGGER)

        self.assertNotIn("result_id", results[0])

    def test_batch_size_mismatch_is_reported(self):
        logger = MagicMock()

        execute(
            ["g"],
            _victim_router(),
            {"batch_size": 32, "bon_params": {"num_concurrent_k": 4}},
            logger,
        )

        warnings = " ".join(str(call.args[0]) for call in logger.warning.call_args_list)
        self.assertIn("pinned to num_concurrent_k", warnings)


if __name__ == "__main__":
    unittest.main()
