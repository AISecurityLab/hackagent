# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for static-template evaluation helpers."""

import logging
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from hackagent.attacks.evaluator.evaluation_step import BaseEvaluationStep
from hackagent.attacks.techniques.config import DEFAULT_JUDGE_IDENTIFIER
from hackagent.attacks.techniques.static_template.static_eval import (
    StaticTemplateEvaluation,
    _build_llm_evaluation_notes,
    _is_execution_error_row,
    _resolve_llm_judges,
    _sync_evaluation_to_server,
    _update_result_status,
    aggregate_results,
    evaluate_responses,
    evaluate_responses_with_llm_judges,
    execute,
)
from hackagent.server.storage.enums import EvaluationStatusEnum


def _logger() -> logging.Logger:
    logger = logging.getLogger("test.static_eval")
    logger.disabled = True
    return logger


class TestIsExecutionErrorRow(unittest.TestCase):
    def test_explicit_is_error_flag(self):
        self.assertTrue(_is_execution_error_row({"is_error": True, "completion": "x"}))

    def test_guardrail_block_is_not_an_execution_error(self):
        self.assertFalse(
            _is_execution_error_row(
                {"guardrail_blocked": True, "error": "blocked", "completion": ""}
            )
        )

    def test_error_with_empty_completion(self):
        self.assertTrue(
            _is_execution_error_row({"error": "timeout", "completion": "  "})
        )
        self.assertTrue(
            _is_execution_error_row({"error_message": "refused", "completion": ""})
        )

    def test_error_with_usable_completion_is_not_an_execution_error(self):
        self.assertFalse(
            _is_execution_error_row({"error": "stale", "completion": "actual answer"})
        )

    def test_clean_row(self):
        self.assertFalse(_is_execution_error_row({"completion": "hello"}))


class TestResolveLlmJudges(unittest.TestCase):
    def test_prefers_judges_list(self):
        judges = [{"identifier": "a", "type": "harmbench"}]
        self.assertEqual(
            _resolve_llm_judges({"judges": judges, "judge": {"x": 1}}), judges
        )

    def test_falls_back_to_judge_dict(self):
        judge = {"identifier": "ollama/llama3", "type": "scorer"}
        self.assertEqual(_resolve_llm_judges({"judge": judge}), [judge])

    def test_falls_back_to_judge_config(self):
        judge_config = {"identifier": "x", "type": "nuanced"}
        self.assertEqual(
            _resolve_llm_judges({"judge_config": judge_config}), [judge_config]
        )

    def test_default_harmbench_judge(self):
        self.assertEqual(
            _resolve_llm_judges({}),
            [{"identifier": DEFAULT_JUDGE_IDENTIFIER, "type": "harmbench"}],
        )

    def test_empty_judges_list_does_not_count_as_configured(self):
        self.assertEqual(
            _resolve_llm_judges({"judges": []})[0]["identifier"],
            DEFAULT_JUDGE_IDENTIFIER,
        )


class TestBuildLlmEvaluationNotes(unittest.TestCase):
    def test_empty_when_no_judge_columns(self):
        self.assertEqual(
            _build_llm_evaluation_notes({"completion": "x"}),
            "LLM judge did not return a parseable score",
        )

    def test_includes_label_score_and_explanation(self):
        notes = _build_llm_evaluation_notes(
            {
                "eval_hb": 1,
                "explanation_hb": "jailbreak",
                "eval_jb": 0,
            }
        )
        self.assertIn("HarmBench=1 (jailbreak)", notes)
        self.assertIn("JailbreakBench=0", notes)
        self.assertNotIn("JailbreakBench=0 (", notes)


class TestEvaluateResponses(unittest.TestCase):
    def test_marks_guardrail_and_error_rows(self):
        data = [
            {"completion": "ok", "goal": "g1"},
            {"guardrail_blocked": True, "completion": "", "goal": "g2"},
            {"error": "timeout", "completion": "", "goal": "g3"},
        ]
        result = evaluate_responses(data, {}, _logger())
        self.assertNotIn("is_error", result[0])
        self.assertEqual(result[1]["evaluation_notes"], "Blocked by guardrail")
        self.assertFalse(result[1]["success"])
        self.assertTrue(result[2]["is_error"])
        self.assertIn("timeout", result[2]["evaluation_notes"])


class TestEvaluateResponsesWithLlmJudges(unittest.TestCase):
    def _step(self, client=None):
        step = MagicMock(spec=BaseEvaluationStep)
        step.client = client
        step.JUDGE_COLUMN_MAP = BaseEvaluationStep.JUDGE_COLUMN_MAP
        step.JUDGE_TYPE_LABELS = BaseEvaluationStep.JUDGE_TYPE_LABELS
        step._build_base_eval_config.return_value = {}
        return step

    def test_guardrail_and_short_rows_skip_judging(self):
        step = self._step(client=MagicMock())
        data = [
            {"attack_prompt": "p1", "completion": "tiny", "goal": "g1"},
            {
                "prompt": "p2",
                "completion": "blocked",
                "guardrail_blocked": True,
                "goal": "g2",
            },
        ]
        result = evaluate_responses_with_llm_judges(
            data, {"min_response_length": 10}, step, _logger()
        )
        step._run_evaluation.assert_not_called()
        self.assertTrue(result[0]["filtered"])
        self.assertEqual(result[0]["evaluation_notes"], "Filtered: response too short")
        self.assertEqual(result[0]["prefix"], "p1")
        self.assertEqual(result[1]["evaluation_notes"], "Blocked by guardrail")
        self.assertFalse(result[1]["success"])

    def test_missing_client_marks_eligible_rows(self):
        step = self._step(client=None)
        data = [{"prefix": "p", "completion": "long enough completion", "goal": "g"}]
        result = evaluate_responses_with_llm_judges(data, {}, step, _logger())
        self.assertFalse(result[0]["success"])
        self.assertIn("No evaluation client", result[0]["evaluation_notes"])
        self.assertNotIn("_static_template_eval_idx", result[0])

    def test_merges_judge_outputs_and_notes(self):
        step = self._step(client=MagicMock())

        def run_eval(rows, judges, base):
            judged = []
            for row in rows:
                updated = dict(row)
                updated["eval_hb"] = 1
                updated["explanation_hb"] = "unsafe"
                updated["success"] = True
                updated["best_score"] = 10.0
                judged.append(updated)
            return judged

        step._run_evaluation.side_effect = run_eval
        data = [
            {"prefix": "p", "completion": "a reasonably long completion", "goal": "g"},
            {"prefix": "p2", "completion": "x", "goal": "g2"},
        ]
        result = evaluate_responses_with_llm_judges(
            data,
            {"min_response_length": 5, "judges": [{"type": "harmbench"}]},
            step,
            _logger(),
        )
        self.assertTrue(result[0]["success"])
        self.assertIn("HarmBench=1 (unsafe)", result[0]["evaluation_notes"])
        self.assertTrue(result[1]["filtered"])
        self.assertNotIn("_static_template_eval_idx", result[0])


class TestAggregateResults(unittest.TestCase):
    def test_empty_input_has_zero_overall_rate(self):
        summary = aggregate_results([], _logger())
        overall = summary[0]
        self.assertEqual(overall["goal"], "OVERALL")
        self.assertEqual(overall["total_attempts"], 0)
        self.assertEqual(overall["success_rate"], 0)

    def test_computes_overall_goal_and_category_metrics(self):
        data = [
            {
                "goal": "g1",
                "template_category": "direct",
                "success": True,
                "response_length": 10,
            },
            {
                "goal": "g1",
                "template_category": "roleplay",
                "success": False,
                "response_length": 20,
            },
            {
                "goal": "g2",
                "template_category": "direct",
                "success": True,
                "response_length": 30,
            },
        ]
        summary = aggregate_results(data, _logger())
        overall = next(row for row in summary if row["goal"] == "OVERALL")
        self.assertEqual(overall["total_attempts"], 3)
        self.assertEqual(overall["successful_attacks"], 2)
        self.assertAlmostEqual(overall["success_rate"], 200 / 3)

        g1 = next(
            row
            for row in summary
            if row["goal"] == "g1" and row["template_category"] == "ALL"
        )
        self.assertEqual(g1["successful_attacks"], 1)
        self.assertEqual(g1["avg_response_length"], 15)

        both = next(
            row
            for row in summary
            if row["goal"] == "g1" and row["template_category"] == "roleplay"
        )
        self.assertEqual(both["successful_attacks"], 0)


class TestSyncAndUpdateHelpers(unittest.TestCase):
    def test_update_result_status_success_and_failure(self):
        backend = MagicMock()
        result_id = str(uuid4())
        self.assertTrue(
            _update_result_status(result_id, True, "ok", backend, _logger())
        )
        self.assertEqual(
            backend.update_result.call_args.kwargs["evaluation_status"],
            EvaluationStatusEnum.SUCCESSFUL_JAILBREAK.value,
        )

        backend.update_result.side_effect = RuntimeError("nope")
        self.assertFalse(
            _update_result_status(result_id, False, "fail", backend, _logger())
        )

    def test_sync_without_backend_or_ids_returns_zero(self):
        self.assertEqual(
            _sync_evaluation_to_server([{"success": True}], {}, _logger()), 0
        )
        self.assertEqual(
            _sync_evaluation_to_server(
                [{"success": True}], {"_backend": MagicMock()}, _logger()
            ),
            0,
        )

    def test_sync_updates_rows_with_result_ids(self):
        backend = MagicMock()
        rid = str(uuid4())
        updated = _sync_evaluation_to_server(
            [
                {"result_id": rid, "success": True, "evaluation_notes": "jb"},
                {"success": False},
            ],
            {"_backend": backend},
            _logger(),
        )
        self.assertEqual(updated, 1)
        backend.update_result.assert_called_once()


class TestStaticTemplateEvaluationExecute(unittest.TestCase):
    def test_execute_wires_judging_sync_and_summary(self):
        step = StaticTemplateEvaluation(
            config={"judges": [{"type": "harmbench", "identifier": "x"}]},
            logger=_logger(),
            client=MagicMock(),
        )
        judged = [
            {
                "goal": "g",
                "template_category": "direct",
                "success": True,
                "response_length": 12,
                "eval_hb": 1,
                "explanation_hb": "yes",
                "prefix": "p",
                "completion": "long enough answer",
            }
        ]
        step._run_evaluation = MagicMock(return_value=judged)
        step._enrich_items_with_scores = MagicMock()
        step._log_evaluation_asr = MagicMock()
        step._build_base_eval_config = MagicMock(return_value={})

        output = step.execute(judged)
        self.assertIn("evaluated", output)
        self.assertIn("summary", output)
        self.assertEqual(output["evaluated"][0]["success"], True)
        self.assertGreaterEqual(len(output["summary"]), 1)

    def test_module_execute_uses_client_from_config(self):
        client = MagicMock()
        with patch.object(
            StaticTemplateEvaluation,
            "execute",
            return_value={"evaluated": [], "summary": []},
        ) as mock_execute:
            result = execute([], {"_client": client}, _logger())
        mock_execute.assert_called_once()
        self.assertEqual(result["evaluated"], [])


if __name__ == "__main__":
    unittest.main()
