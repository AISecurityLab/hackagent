# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for typed attack result models and row conversion helpers."""

import unittest

from pydantic import ValidationError

from hackagent.attacks.types import (
    AttackResult,
    Evaluation,
    attack_results_to_rows,
    flatten_run_result,
    rows_to_attack_results,
)


class TestEvaluation(unittest.TestCase):
    def test_defaults_and_round_trip(self):
        evaluation = Evaluation(name="harmbench", score=1.0, success=True, notes="ok")
        self.assertEqual(evaluation.name, "harmbench")
        self.assertEqual(evaluation.score, 1.0)
        self.assertTrue(evaluation.success)
        self.assertEqual(evaluation.notes, "ok")
        self.assertEqual(evaluation.metadata, {})

    def test_frozen(self):
        evaluation = Evaluation(name="jb")
        with self.assertRaises(ValidationError):
            evaluation.name = "other"

    def test_rejects_unknown_fields(self):
        with self.assertRaises(ValidationError):
            Evaluation(name="jb", classification="SUCCESS")


class TestAttackResultFromRow(unittest.TestCase):
    def test_passthrough_existing_instance(self):
        original = AttackResult(goal="g", prompt="p", response="r")
        self.assertIs(AttackResult.from_row(original), original)

    def test_prefix_and_completion_aliases(self):
        result = AttackResult.from_row(
            {"goal": "leak secrets", "prefix": "Sure,", "completion": "here it is"}
        )
        self.assertEqual(result.goal, "leak secrets")
        self.assertEqual(result.prompt, "Sure,")
        self.assertEqual(result.response, "here it is")
        self.assertEqual(result.metadata["prefix"], "Sure,")
        self.assertEqual(result.metadata["completion"], "here it is")

    def test_prompt_and_response_take_precedence_over_aliases(self):
        result = AttackResult.from_row(
            {
                "prompt": "canonical prompt",
                "prefix": "ignored prefix",
                "response": "canonical response",
                "completion": "ignored completion",
            }
        )
        self.assertEqual(result.prompt, "canonical prompt")
        self.assertEqual(result.response, "canonical response")

    def test_non_dict_row_is_preserved_as_raw_metadata(self):
        result = AttackResult.from_row("legacy-string-row")
        self.assertEqual(result.goal, "")
        self.assertEqual(result.metadata, {"_raw": "legacy-string-row"})

    def test_none_like_goal_becomes_empty_string(self):
        result = AttackResult.from_row({"goal": None, "prompt": None, "response": None})
        self.assertEqual(result.goal, "")
        self.assertEqual(result.prompt, "")
        self.assertEqual(result.response, "")

    def test_evaluation_instances_are_kept(self):
        evaluation = Evaluation(name="hb", score=0.0, success=False)
        result = AttackResult.from_row({"evaluations": [evaluation]})
        self.assertEqual(len(result.evaluations), 1)
        self.assertIs(result.evaluations[0], evaluation)

    def test_schema_matching_evaluation_dicts(self):
        result = AttackResult.from_row(
            {
                "evaluations": [
                    {"name": "hb", "score": 1, "success": True, "notes": "jailbreak"}
                ]
            }
        )
        self.assertEqual(result.evaluations[0].name, "hb")
        self.assertEqual(result.evaluations[0].score, 1)
        self.assertTrue(result.evaluations[0].success)

    def test_opaque_evaluation_dicts_are_stored_as_metadata(self):
        result = AttackResult.from_row(
            {"evaluations": [{"classification": "SUCCESS", "rationale": "ok"}]}
        )
        evaluation = result.evaluations[0]
        self.assertEqual(evaluation.name, "")
        self.assertIsNone(evaluation.score)
        self.assertEqual(
            evaluation.metadata, {"classification": "SUCCESS", "rationale": "ok"}
        )

    def test_non_list_evaluations_are_ignored(self):
        result = AttackResult.from_row({"evaluations": {"name": "hb"}})
        self.assertEqual(result.evaluations, [])


class TestAttackResultToRow(unittest.TestCase):
    def test_round_trips_canonical_fields_and_extra_metadata(self):
        result = AttackResult.from_row(
            {"goal": "g", "prompt": "p", "response": "r", "template": "direct"}
        )
        row = result.to_row()
        self.assertEqual(row["goal"], "g")
        self.assertEqual(row["prompt"], "p")
        self.assertEqual(row["response"], "r")
        self.assertEqual(row["template"], "direct")
        self.assertNotIn("evaluations", row)

    def test_schema_evaluations_dump_as_model_fields(self):
        result = AttackResult(
            evaluations=[Evaluation(name="hb", score=1.0, success=True, notes="yes")]
        )
        dumped = result.to_row()["evaluations"][0]
        self.assertEqual(dumped["name"], "hb")
        self.assertEqual(dumped["score"], 1.0)
        self.assertTrue(dumped["success"])
        self.assertEqual(dumped["notes"], "yes")

    def test_opaque_evaluations_round_trip_flat(self):
        original = {"classification": "SUCCESS", "rationale": "ok"}
        result = AttackResult.from_row({"evaluations": [original]})
        dumped = result.to_row()["evaluations"][0]
        self.assertEqual(dumped, original)
        self.assertNotIn("metadata", dumped)

    def test_frozen_model_cannot_be_mutated(self):
        result = AttackResult(goal="g")
        with self.assertRaises(ValidationError):
            result.goal = "other"


class TestExtractAndNormalize(unittest.TestCase):
    def test_flatten_none_and_non_container(self):
        self.assertEqual(flatten_run_result(None), [])
        self.assertEqual(flatten_run_result("not-a-batch"), [])
        self.assertEqual(flatten_run_result(42), [])

    def test_flatten_list_passthrough(self):
        rows = [{"goal": "a"}, {"goal": "b"}]
        self.assertEqual(flatten_run_result(rows), rows)

    def test_flatten_prefers_evaluated_over_other_keys(self):
        evaluated = [{"goal": "evaluated"}]
        rows = [{"goal": "rows"}]
        self.assertEqual(
            flatten_run_result({"evaluated": evaluated, "rows": rows}),
            evaluated,
        )

    def test_flatten_falls_back_through_legacy_keys(self):
        for key in ("rows", "results", "data", "items"):
            payload = [{key: True}]
            self.assertEqual(flatten_run_result({key: payload}), payload)

    def test_flatten_ignores_non_list_legacy_values(self):
        self.assertEqual(flatten_run_result({"rows": {"goal": "x"}}), [])
        self.assertEqual(flatten_run_result({"evaluated": "not-a-list"}), [])
        self.assertEqual(flatten_run_result({"summary": [1]}), [])

    def test_rows_to_attack_results_converts_extracted_rows(self):
        results = rows_to_attack_results({"data": [{"goal": "g1", "completion": "c1"}]})
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], AttackResult)
        self.assertEqual(results[0].goal, "g1")
        self.assertEqual(results[0].response, "c1")

    def test_attack_results_to_rows_passthrough_legacy_items(self):
        typed = AttackResult(goal="g", prompt="p")
        mixed = attack_results_to_rows([typed, {"already": "a dict"}, "raw"])
        self.assertEqual(mixed[0]["goal"], "g")
        self.assertEqual(mixed[1], {"already": "a dict"})
        self.assertEqual(mixed[2], "raw")


if __name__ == "__main__":
    unittest.main()
