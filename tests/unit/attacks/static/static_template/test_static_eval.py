# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the static template / baseline evaluation module."""

import logging
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from hackagent.core.defaults import DEFAULT_JUDGE_IDENTIFIER
from hackagent.attacks.techniques.static.static_template import static_eval
from hackagent.attacks.techniques.static.static_template.static_eval import (
    StaticTemplateEvaluation,
    _build_llm_evaluation_notes,
    _finalize_goals_with_tracker,
    _is_execution_error_row,
    _resolve_llm_judges,
    _sync_evaluation_to_server,
    _update_result_status,
    aggregate_results,
    evaluate_responses,
    evaluate_responses_with_llm_judges,
    execute,
)
from hackagent.core.contracts import EvalStatus

LOGGER = logging.getLogger("test.static_template.eval")
LOGGER.addHandler(logging.NullHandler())


def _evaluator_step(client=MagicMock(), judged=None):
    """Stand-in for BaseEvaluationStep used by the LLM judge path."""
    step = MagicMock()
    step.client = client
    step._build_base_eval_config.return_value = {"base": True}
    step._run_evaluation.side_effect = lambda rows, judges, cfg: (
        judged if judged is not None else [dict(row, success=True) for row in rows]
    )
    return step


def _context(goal, goal_index=0, finalized=False, result_id=None):
    return SimpleNamespace(
        goal=goal,
        goal_index=goal_index,
        is_finalized=finalized,
        result_id=result_id or str(uuid4()),
    )


def _tracker(contexts):
    tracker = MagicMock()
    tracker.get_all_contexts.return_value = contexts
    tracker.finalize_goal.return_value = True
    tracker.get_summary.return_value = {
        "successful_attacks": 1,
        "total_goals": 1,
        "success_rate": 100.0,
        "total_traces": 3,
    }
    return tracker


class TestIsExecutionErrorRow(unittest.TestCase):
    def test_explicit_error_flag_wins(self):
        self.assertTrue(_is_execution_error_row({"is_error": True}))

    def test_guardrail_blocks_are_not_execution_errors(self):
        self.assertFalse(
            _is_execution_error_row({"guardrail_blocked": True, "error": "blocked"})
        )

    def test_error_without_completion_is_an_execution_error(self):
        self.assertTrue(_is_execution_error_row({"error": "timeout", "completion": ""}))
        self.assertTrue(_is_execution_error_row({"error_message": "boom"}))

    def test_error_with_a_completion_is_not_an_execution_error(self):
        self.assertFalse(
            _is_execution_error_row({"error": "warn", "completion": "text"})
        )

    def test_clean_rows_are_not_errors(self):
        self.assertFalse(_is_execution_error_row({"completion": "text"}))


class TestResolveLlmJudges(unittest.TestCase):
    def test_judges_list_is_used_first(self):
        judges = [{"identifier": "a"}, {"identifier": "b"}]

        self.assertEqual(_resolve_llm_judges({"judges": judges}), judges)

    def test_single_judge_is_wrapped(self):
        self.assertEqual(
            _resolve_llm_judges({"judge": {"identifier": "j"}}), [{"identifier": "j"}]
        )

    def test_legacy_judge_config_key_is_supported(self):
        self.assertEqual(
            _resolve_llm_judges({"judge_config": {"identifier": "j"}}),
            [{"identifier": "j"}],
        )

    def test_default_harmbench_judge_is_the_fallback(self):
        judges = _resolve_llm_judges({})

        self.assertEqual(judges[0]["identifier"], DEFAULT_JUDGE_IDENTIFIER)
        self.assertEqual(judges[0]["type"], "harmbench")

    def test_empty_judges_list_falls_through(self):
        judges = _resolve_llm_judges({"judges": []})

        self.assertEqual(judges[0]["type"], "harmbench")


class TestBuildLlmEvaluationNotes(unittest.TestCase):
    def test_scores_and_explanations_are_combined(self):
        notes = _build_llm_evaluation_notes(
            {"eval_hb": 1, "explanation_hb": "complied", "eval_jb": 0}
        )

        self.assertIn("HarmBench=1 (complied)", notes)
        self.assertIn("JailbreakBench=0", notes)
        self.assertIn(" | ", notes)

    def test_missing_scores_produce_a_placeholder(self):
        self.assertEqual(
            _build_llm_evaluation_notes({"completion": "x"}),
            "LLM judge did not return a parseable score",
        )


class TestEvaluateResponsesWithLlmJudges(unittest.TestCase):
    def test_guardrail_rows_bypass_the_judges(self):
        step = _evaluator_step()

        results = evaluate_responses_with_llm_judges(
            [{"goal": "g", "guardrail_blocked": True}], {}, step, LOGGER
        )

        self.assertFalse(results[0]["success"])
        self.assertEqual(results[0]["evaluation_notes"], "Blocked by guardrail")
        step._run_evaluation.assert_not_called()

    def test_short_responses_are_filtered_before_judging(self):
        step = _evaluator_step()

        results = evaluate_responses_with_llm_judges(
            [{"goal": "g", "completion": "no"}],
            {"min_response_length": 10},
            step,
            LOGGER,
        )

        self.assertTrue(results[0]["filtered"])
        self.assertEqual(results[0]["evaluation_notes"], "Filtered: response too short")
        step._run_evaluation.assert_not_called()

    def test_prefix_is_derived_from_the_attack_prompt(self):
        step = _evaluator_step()

        evaluate_responses_with_llm_judges(
            [{"goal": "g", "attack_prompt": "p", "completion": "a long completion"}],
            {},
            step,
            LOGGER,
        )

        judged_rows = step._run_evaluation.call_args.args[0]
        self.assertEqual(judged_rows[0]["prefix"], "p")

    def test_prompt_key_is_the_last_prefix_fallback(self):
        step = _evaluator_step()

        evaluate_responses_with_llm_judges(
            [{"goal": "g", "prompt": "from prompt", "completion": "a long completion"}],
            {},
            step,
            LOGGER,
        )

        self.assertEqual(
            step._run_evaluation.call_args.args[0][0]["prefix"], "from prompt"
        )

    def test_missing_evaluation_client_marks_rows_unevaluated(self):
        step = _evaluator_step(client=None)

        results = evaluate_responses_with_llm_judges(
            [{"goal": "g", "completion": "a long completion"}], {}, step, LOGGER
        )

        self.assertFalse(results[0]["success"])
        self.assertEqual(
            results[0]["evaluation_notes"], "No evaluation client available for judges"
        )
        self.assertNotIn("_static_template_eval_idx", results[0])

    def test_judged_rows_are_merged_back_in_input_order(self):
        rows = [
            {"goal": "g0", "completion": "a long completion"},
            {"goal": "g1", "completion": "short", "response_length": 50},
        ]
        step = _evaluator_step()

        results = evaluate_responses_with_llm_judges(rows, {}, step, LOGGER)

        self.assertEqual([r["goal"] for r in results], ["g0", "g1"])
        for row in results:
            self.assertNotIn("_static_template_eval_idx", row)
            self.assertTrue(row["success"])

    def test_evaluation_notes_are_built_from_judge_columns(self):
        step = _evaluator_step(
            judged=[
                {
                    "goal": "g",
                    "_static_template_eval_idx": 0,
                    "eval_hb": 1,
                    "explanation_hb": "complied",
                    "success": True,
                }
            ]
        )

        results = evaluate_responses_with_llm_judges(
            [{"goal": "g", "completion": "a long completion"}], {}, step, LOGGER
        )

        self.assertIn("HarmBench=1", results[0]["evaluation_notes"])

    def test_response_length_is_computed_when_absent(self):
        step = _evaluator_step()

        results = evaluate_responses_with_llm_judges(
            [{"goal": "g", "completion": "abcdefghijk"}], {}, step, LOGGER
        )

        self.assertEqual(results[0]["response_length"], 11)

    def test_input_rows_are_not_mutated(self):
        original = {"goal": "g", "completion": "a long completion"}
        step = _evaluator_step()

        evaluate_responses_with_llm_judges([original], {}, step, LOGGER)

        self.assertEqual(original, {"goal": "g", "completion": "a long completion"})


class TestEvaluateResponses(unittest.TestCase):
    def test_execution_errors_are_flagged(self):
        rows = [{"goal": "g", "error": "timeout", "completion": ""}]

        evaluate_responses(rows, {}, LOGGER)

        self.assertTrue(rows[0]["is_error"])
        self.assertFalse(rows[0]["success"])
        self.assertEqual(rows[0]["best_score"], 0.0)
        self.assertIn("timeout", rows[0]["evaluation_notes"])

    def test_unknown_error_text_is_used_when_absent(self):
        rows = [{"goal": "g", "is_error": True}]

        evaluate_responses(rows, {}, LOGGER)

        self.assertIn("Unknown error", rows[0]["evaluation_notes"])

    def test_guardrail_rows_get_defaults_without_being_overwritten(self):
        rows = [{"guardrail_blocked": True, "success": True}]

        evaluate_responses(rows, {}, LOGGER)

        self.assertTrue(rows[0]["success"])
        self.assertEqual(rows[0]["evaluation_notes"], "Blocked by guardrail")

    def test_healthy_rows_are_left_alone(self):
        rows = [{"goal": "g", "completion": "fine"}]

        evaluate_responses(rows, {}, LOGGER)

        self.assertNotIn("is_error", rows[0])


class TestAggregateResults(unittest.TestCase):
    def test_empty_input_produces_only_the_overall_row(self):
        summary = aggregate_results([], LOGGER)

        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["goal"], "OVERALL")
        self.assertEqual(summary[0]["success_rate"], 0)

    def test_overall_success_rate_is_computed(self):
        data = [
            {"goal": "g1", "template_category": "roleplay", "success": True},
            {"goal": "g1", "template_category": "dan", "success": False},
        ]

        summary = aggregate_results(data, LOGGER)

        self.assertEqual(summary[0]["total_attempts"], 2)
        self.assertEqual(summary[0]["successful_attacks"], 1)
        self.assertEqual(summary[0]["success_rate"], 50.0)

    def test_per_goal_rows_include_average_response_length(self):
        data = [
            {"goal": "g1", "success": True, "response_length": 100},
            {"goal": "g1", "success": False, "response_length": 50},
        ]

        summary = aggregate_results(data, LOGGER)
        goal_rows = [
            r for r in summary if r["goal"] == "g1" and r["template_category"] == "ALL"
        ]

        self.assertEqual(goal_rows[0]["avg_response_length"], 75)

    def test_per_category_and_combination_rows_are_emitted(self):
        data = [
            {"goal": "g1", "template_category": "dan", "success": True},
            {"goal": "g2", "template_category": "dan", "success": False},
        ]

        summary = aggregate_results(data, LOGGER)

        category_rows = [r for r in summary if r["goal"] == "ALL"]
        self.assertEqual(category_rows[0]["template_category"], "dan")
        self.assertEqual(category_rows[0]["total_attempts"], 2)

        combo_rows = [
            r for r in summary if r["goal"] == "g1" and r["template_category"] == "dan"
        ]
        self.assertEqual(combo_rows[0]["success_rate"], 100.0)

    def test_missing_fields_fall_back_to_unknown(self):
        summary = aggregate_results([{"success": False}], LOGGER)

        self.assertTrue(any(r["goal"] == "unknown" for r in summary))
        self.assertTrue(any(r["template_category"] == "unknown" for r in summary))


class TestUpdateResultStatus(unittest.TestCase):
    def test_successful_jailbreak_status_is_written(self):
        backend = MagicMock()
        result_id = str(uuid4())

        ok = _update_result_status(result_id, True, "notes", backend, LOGGER)

        self.assertTrue(ok)
        backend.update_result.assert_called_once_with(
            result_id=UUID(result_id),
            evaluation_status=EvalStatus.SUCCESSFUL_JAILBREAK.value,
            evaluation_notes="notes",
        )

    def test_failed_jailbreak_status_is_written(self):
        backend = MagicMock()

        _update_result_status(str(uuid4()), False, "notes", backend, LOGGER)

        self.assertEqual(
            backend.update_result.call_args.kwargs["evaluation_status"],
            EvalStatus.FAILED_JAILBREAK.value,
        )

    def test_invalid_uuid_is_reported_as_failure(self):
        backend = MagicMock()

        self.assertFalse(
            _update_result_status("not-a-uuid", True, "notes", backend, LOGGER)
        )
        backend.update_result.assert_not_called()

    def test_backend_errors_are_reported_as_failure(self):
        backend = MagicMock()
        backend.update_result.side_effect = RuntimeError("db down")

        self.assertFalse(
            _update_result_status(str(uuid4()), True, "n", backend, LOGGER)
        )


class TestSyncEvaluationToServer(unittest.TestCase):
    def test_tracker_path_is_preferred(self):
        tracker = MagicMock()

        with patch.object(
            static_eval, "_finalize_goals_with_tracker", return_value=3
        ) as finalize:
            count = _sync_evaluation_to_server([], {}, LOGGER, goal_tracker=tracker)

        self.assertEqual(count, 3)
        self.assertIs(finalize.call_args.args[1], tracker)

    def test_tracker_can_come_from_the_config(self):
        tracker = MagicMock()

        with patch.object(
            static_eval, "_finalize_goals_with_tracker", return_value=1
        ) as finalize:
            _sync_evaluation_to_server([], {"_tracker": tracker}, LOGGER)

        self.assertIs(finalize.call_args.args[1], tracker)

    def test_without_a_backend_nothing_is_synced(self):
        self.assertEqual(
            _sync_evaluation_to_server([{"result_id": "x"}], {}, LOGGER), 0
        )

    def test_without_result_ids_nothing_is_synced(self):
        backend = MagicMock()

        count = _sync_evaluation_to_server(
            [{"goal": "g"}], {"_backend": backend}, LOGGER
        )

        self.assertEqual(count, 0)
        backend.update_result.assert_not_called()

    def test_legacy_rows_are_updated_individually(self):
        backend = MagicMock()
        rows = [
            {"result_id": str(uuid4()), "success": True, "evaluation_notes": "ok"},
            {"goal": "no id"},
        ]

        count = _sync_evaluation_to_server(rows, {"_client": backend}, LOGGER)

        self.assertEqual(count, 1)
        backend.update_result.assert_called_once()


class TestFinalizeGoalsWithTracker(unittest.TestCase):
    def test_goal_with_a_success_is_finalized_as_successful(self):
        ctx = _context("g1", goal_index=0)
        tracker = _tracker({0: ctx})
        rows = [
            {
                "goal": "g1",
                "goal_index": 0,
                "success": True,
                "template_category": "dan",
            },
            {"goal": "g1", "goal_index": 0, "success": False},
        ]

        finalized = _finalize_goals_with_tracker(rows, tracker, LOGGER)

        self.assertEqual(finalized, 1)
        call = tracker.finalize_goal.call_args.kwargs
        self.assertTrue(call["success"])
        self.assertEqual(call["final_metadata"]["successful_attempts"], 1)
        self.assertEqual(call["final_metadata"]["success_rate"], 50.0)
        self.assertIsNone(call["evaluation_status"])

    def test_evaluation_trace_carries_per_attempt_details(self):
        ctx = _context("g1")
        tracker = _tracker({0: ctx})
        rows = [
            {
                "goal": "g1",
                "goal_index": 0,
                "success": True,
                "eval_hb": 1,
                "explanation_hb": "complied",
                "completion": "text",
            }
        ]

        _finalize_goals_with_tracker(rows, tracker, LOGGER, evaluator_name="custom")

        trace = tracker.add_evaluation_trace.call_args.kwargs
        self.assertEqual(trace["evaluator_name"], "custom")
        self.assertEqual(trace["score"], 100.0)
        detail = trace["evaluation_result"]["evaluations"][0]
        self.assertEqual(detail["eval_hb"], 1)
        self.assertEqual(detail["explanation_hb"], "complied")

    def test_goals_without_rows_get_a_no_prompt_trace(self):
        ctx = _context("lonely goal", goal_index=2)
        tracker = _tracker({2: ctx})

        _finalize_goals_with_tracker([], tracker, LOGGER)

        trace = tracker.add_custom_trace.call_args.kwargs
        self.assertEqual(trace["step_name"], "No Prompt Generated")
        self.assertIn(
            "no prompts/completions generated",
            tracker.finalize_goal.call_args.kwargs["evaluation_notes"],
        )

    def test_all_error_rows_produce_an_agent_error_status(self):
        ctx = _context("g1")
        tracker = _tracker({0: ctx})
        rows = [
            {"goal": "g1", "goal_index": 0, "success": False, "is_error": True},
            {"goal": "g1", "goal_index": 0, "success": False, "error": "boom"},
        ]

        _finalize_goals_with_tracker(rows, tracker, LOGGER)

        call = tracker.finalize_goal.call_args.kwargs
        self.assertEqual(call["evaluation_status"], EvalStatus.ERROR_AGENT_RESPONSE)
        self.assertFalse(call["success"])
        self.assertIn("execution/adapter errors", call["evaluation_notes"])

    def test_already_finalized_goals_are_skipped(self):
        ctx = _context("g1", finalized=True)
        tracker = _tracker({0: ctx})

        finalized = _finalize_goals_with_tracker(
            [{"goal": "g1", "goal_index": 0, "success": True}], tracker, LOGGER
        )

        self.assertEqual(finalized, 0)
        tracker.finalize_goal.assert_not_called()

    def test_failed_finalization_is_not_counted(self):
        ctx = _context("g1")
        tracker = _tracker({0: ctx})
        tracker.finalize_goal.return_value = False

        finalized = _finalize_goals_with_tracker(
            [{"goal": "g1", "goal_index": 0, "success": True}], tracker, LOGGER
        )

        self.assertEqual(finalized, 0)

    def test_goals_are_finalized_in_index_order(self):
        contexts = {1: _context("g1", 1), 0: _context("g0", 0)}
        tracker = _tracker(contexts)

        _finalize_goals_with_tracker([], tracker, LOGGER)

        finalized_goals = [
            call.kwargs["ctx"].goal for call in tracker.finalize_goal.call_args_list
        ]
        self.assertEqual(finalized_goals, ["g0", "g1"])


class TestStaticTemplateEvaluationExecute(unittest.TestCase):
    def test_pipeline_runs_judging_sync_and_aggregation(self):
        step = StaticTemplateEvaluation(
            config={"goals": ["g"]}, logger=LOGGER, client=MagicMock()
        )
        evaluated = [{"goal": "g", "success": True}]

        with (
            patch.object(
                static_eval,
                "evaluate_responses_with_llm_judges",
                return_value=evaluated,
            ) as judge,
            patch.object(static_eval, "_sync_evaluation_to_server") as sync,
            patch.object(step, "_log_evaluation_asr") as log_asr,
        ):
            out = step.execute([{"goal": "g"}], goal_tracker="tracker")

        judge.assert_called_once()
        log_asr.assert_called_once_with(evaluated)
        self.assertEqual(sync.call_args.kwargs["evaluator_name"], "baseline_llm_judge")
        self.assertEqual(out["evaluated"], evaluated)
        self.assertEqual(out["summary"][0]["goal"], "OVERALL")

    def test_module_level_execute_builds_the_step_with_a_client(self):
        backend = MagicMock()

        with patch.object(static_eval, "StaticTemplateEvaluation") as cls:
            cls.return_value.execute.return_value = {"evaluated": [], "summary": []}
            execute([], {"_backend": backend}, LOGGER)

        self.assertIs(cls.call_args.kwargs["client"], backend)

    def test_explicit_client_wins_over_the_config(self):
        explicit = MagicMock()

        with patch.object(static_eval, "StaticTemplateEvaluation") as cls:
            cls.return_value.execute.return_value = {"evaluated": [], "summary": []}
            execute([], {"_backend": MagicMock()}, LOGGER, client=explicit)

        self.assertIs(cls.call_args.kwargs["client"], explicit)


if __name__ == "__main__":
    unittest.main()
