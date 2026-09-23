# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the PAP attack loop, tracing and orchestration."""

import logging
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.pap import generation as papgen
from hackagent.attacks.techniques.pap.generation import (
    _attack_single_goal,
    _persist_technique_trace,
    execute,
)

_THREE_TECHNIQUES = [
    "Logical Appeal",
    "Expert Endorsement",
    "Authority Endorsement",
]

LOGGER = logging.getLogger("test.pap.generation")
LOGGER.addHandler(logging.NullHandler())


def _router(response=None, side_effect=None, agent_id="agent-id"):
    router = MagicMock()
    router.backend_agent = SimpleNamespace(id=agent_id)
    if side_effect is not None:
        router.route_request.side_effect = side_effect
    else:
        router.route_request.return_value = response or {"generated_text": "text"}
    return router


def _judge(verdicts):
    judge = MagicMock()
    judge.available = True
    judge.judge_count = 1
    judge.is_jailbreak.side_effect = list(verdicts)
    return judge


def _attack(**overrides):
    kwargs = {
        "goal": "the goal",
        "goal_idx": 0,
        "techniques": ["Logical Appeal"],
        "pap_params": {},
        "target_max_tokens": 256,
        "target_temperature": 0.6,
        "target_timeout": 30,
        "attacker_router": _router({"generated_text": "persuasive version"}),
        "attacker_key": "attacker-id",
        "agent_router": _router({"generated_text": "victim answer"}),
        "victim_key": "victim-id",
        "step_judge": None,
        "tracker": None,
        "logger": LOGGER,
    }
    kwargs.update(overrides)
    return _attack_single_goal(**kwargs)


class TestAttackSingleGoal(unittest.TestCase):
    def test_single_technique_produces_a_result(self):
        result = _attack()

        self.assertEqual(result["goal"], "the goal")
        self.assertEqual(result["response"], "victim answer")
        self.assertEqual(result["technique"], "Logical Appeal")
        self.assertEqual(result["technique_index"], 0)
        self.assertFalse(result["success"])

    def test_attacker_and_target_request_parameters(self):
        attacker = _router({"generated_text": "persuasive"})
        victim = _router()

        _attack(
            attacker_router=attacker,
            agent_router=victim,
            pap_params={"attacker_temperature": 0.2, "attacker_max_tokens": 64},
            target_max_tokens=128,
            target_temperature=0.1,
            target_timeout=9,
        )

        attacker_request = attacker.route_request.call_args.kwargs["request_data"]
        self.assertEqual(attacker_request["temperature"], 0.2)
        self.assertEqual(attacker_request["max_tokens"], 64)
        target_request = victim.route_request.call_args.kwargs["request_data"]
        self.assertEqual(target_request["max_tokens"], 128)
        self.assertEqual(target_request["temperature"], 0.1)
        self.assertEqual(target_request["timeout"], 9)

    def test_empty_attacker_output_skips_the_technique(self):
        attacker = _router({"generated_text": "", "error_message": "no capacity"})
        victim = _router()

        result = _attack(attacker_router=attacker, agent_router=victim)

        victim.route_request.assert_not_called()
        self.assertIsNone(result["response"])

    def test_attacker_exception_skips_the_technique(self):
        attacker = _router(side_effect=RuntimeError("attacker down"))
        victim = _router()

        result = _attack(attacker_router=attacker, agent_router=victim)

        victim.route_request.assert_not_called()
        self.assertIsNone(result["technique"])

    def test_target_exception_is_recorded(self):
        victim = _router(side_effect=RuntimeError("target down"))

        result = _attack(agent_router=victim)

        self.assertIsNone(result["response"])
        self.assertFalse(result["success"])

    def test_jailbreak_stops_the_technique_loop(self):
        victim = _router()
        judge = _judge([(True, 1.0, {"eval_hb": 1})])

        result = _attack(
            techniques=_THREE_TECHNIQUES, agent_router=victim, step_judge=judge
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["technique"], _THREE_TECHNIQUES[0])
        self.assertEqual(result["eval_hb"], 1)
        self.assertEqual(victim.route_request.call_count, 1)

    def test_all_techniques_are_tried_without_a_jailbreak(self):
        victim = _router()
        judge = _judge([(False, 0.1, {}), (False, 0.4, {}), (False, 0.2, {})])

        result = _attack(
            techniques=_THREE_TECHNIQUES, agent_router=victim, step_judge=judge
        )

        self.assertEqual(victim.route_request.call_count, 3)
        self.assertEqual(result["technique"], _THREE_TECHNIQUES[1])
        self.assertEqual(result["best_score"], 0.4)

    def test_first_valid_response_is_kept_when_all_scores_are_zero(self):
        victim = _router()
        judge = _judge([(False, 0.0, {}), (False, 0.0, {})])

        result = _attack(
            techniques=_THREE_TECHNIQUES[:2], agent_router=victim, step_judge=judge
        )

        self.assertEqual(result["technique"], _THREE_TECHNIQUES[0])
        self.assertEqual(result["response"], "text")

    def test_judge_is_skipped_without_a_response(self):
        victim = _router({"error_message": "timeout"})
        judge = _judge([(True, 1.0, {})])

        result = _attack(agent_router=victim, step_judge=judge)

        judge.is_jailbreak.assert_not_called()
        self.assertFalse(result["success"])

    def test_guardrail_blocks_are_not_errors(self):
        victim = _router(
            {
                "adapter_type": "guardrail",
                "agent_specific_data": {"side": "output"},
            }
        )
        tracker = MagicMock()
        tracker.get_goal_context.return_value = SimpleNamespace(result_id="r")

        _attack(agent_router=victim, tracker=tracker)

        candidate = tracker.add_interaction_trace.call_args_list[0].kwargs
        self.assertEqual(candidate["response"]["adapter_type"], "guardrail")

    def test_traces_are_written_for_successful_techniques(self):
        tracker = MagicMock()
        tracker.get_goal_context.return_value = SimpleNamespace(result_id="r")

        _attack(tracker=tracker)

        names = [
            call.kwargs["step_name"]
            for call in tracker.add_interaction_trace.call_args_list
        ]
        self.assertTrue(any(name.startswith("PAP Technique 1/1") for name in names))
        self.assertIn("Evaluation – Technique 1/1", names)

    def test_traces_are_written_when_the_attacker_fails(self):
        tracker = MagicMock()
        tracker.get_goal_context.return_value = SimpleNamespace(result_id="r")
        attacker = _router({"generated_text": ""})

        _attack(attacker_router=attacker, tracker=tracker)

        candidate = tracker.add_interaction_trace.call_args_list[0].kwargs
        self.assertIsNone(candidate["request"]["prompt"])

    def test_no_traces_without_a_goal_context(self):
        tracker = MagicMock()
        tracker.get_goal_context.return_value = None

        _attack(tracker=tracker)

        tracker.add_interaction_trace.assert_not_called()


class TestPersistTechniqueTrace(unittest.TestCase):
    def _persist(self, **overrides):
        tracker = MagicMock()
        kwargs = {
            "tracker": tracker,
            "goal_ctx": "ctx",
            "tech_idx": 0,
            "total_techniques": 3,
            "technique": "Logical Appeal",
            "persuasive_prompt": "please consider",
            "response_text": "sure thing",
            "error": None,
            "judge_score": 1.0,
            "is_jailbreak": True,
            "judge_cols": {"eval_hb": 1, "explanation_hb": "complied"},
        }
        kwargs.update(overrides)
        _persist_technique_trace(**kwargs)
        return tracker

    def test_candidate_trace_carries_prompt_and_response(self):
        tracker = self._persist()

        candidate = tracker.add_interaction_trace.call_args_list[0].kwargs
        self.assertTrue(
            candidate["step_name"].startswith("PAP Technique 1/3: Logical Appeal")
        )
        self.assertEqual(candidate["request"]["prompt"], "please consider")
        self.assertEqual(candidate["response"]["generated_text"], "sure thing")
        self.assertEqual(candidate["metadata"]["response_length"], 10)

    def test_evaluation_trace_summarises_the_verdict(self):
        tracker = self._persist()

        evaluation = tracker.add_interaction_trace.call_args_list[1].kwargs
        verdict = evaluation["response"]["generated_text"]
        self.assertIn("Technique: Logical Appeal", verdict)
        self.assertIn("Jailbreak: YES", verdict)
        self.assertIn("Explanation: complied", verdict)
        self.assertIn("sure thing", verdict)

    def test_failed_technique_trace_has_no_response(self):
        tracker = self._persist(
            persuasive_prompt=None,
            response_text=None,
            error="attacker offline",
            judge_score=0.0,
            is_jailbreak=False,
            judge_cols={},
        )

        candidate = tracker.add_interaction_trace.call_args_list[0].kwargs
        self.assertEqual(candidate["response"]["error_message"], "attacker offline")
        self.assertEqual(candidate["metadata"]["response_length"], 0)
        verdict = tracker.add_interaction_trace.call_args_list[1].kwargs["response"][
            "generated_text"
        ]
        self.assertIn("Jailbreak: NO", verdict)

    def test_guardrail_info_replaces_the_response_payload(self):
        tracker = self._persist(guardrail_info={"side": "input"})

        candidate = tracker.add_interaction_trace.call_args_list[0].kwargs
        self.assertEqual(candidate["response"]["adapter_type"], "guardrail")
        self.assertEqual(
            candidate["response"]["agent_specific_data"], {"side": "input"}
        )


class TestExecute(unittest.TestCase):
    def setUp(self):
        attack_patch = patch.object(papgen, "_attack_single_goal")
        self.attack = attack_patch.start()
        self.addCleanup(attack_patch.stop)
        self.attack.side_effect = lambda **kwargs: {
            "goal": kwargs["goal"],
            "response": "answer",
            "success": False,
            "best_score": 0.0,
        }
        router_patch = patch.object(
            papgen, "_create_attacker_router", return_value=_router(agent_id="att-id")
        )
        self.create_attacker = router_patch.start()
        self.addCleanup(router_patch.stop)

    def _config(self, **extra):
        config = {"attacker": {"identifier": "attacker-model"}, "_backend": MagicMock()}
        config.update(extra)
        return config

    def test_one_result_per_goal(self):
        results = execute(["g0", "g1"], _router(), self._config(), LOGGER)

        self.assertEqual([r["goal"] for r in results], ["g0", "g1"])
        for row in results:
            self.assertIn("generation_elapsed_s", row)

    def test_attacker_configuration_is_required(self):
        with self.assertRaises(ValueError):
            execute(["g"], _router(), {"attacker": {}}, LOGGER)

    def test_attacker_router_failures_propagate(self):
        self.create_attacker.side_effect = RuntimeError("bad endpoint")

        with self.assertRaises(RuntimeError):
            execute(["g"], _router(), self._config(), LOGGER)

    def test_technique_count_can_be_capped(self):
        execute(
            ["g"],
            _router(),
            self._config(pap_params={"max_techniques_per_goal": 2}),
            LOGGER,
        )

        self.assertEqual(len(self.attack.call_args.kwargs["techniques"]), 2)

    def test_target_sampling_parameters_are_coerced(self):
        execute(
            ["g"],
            _router(),
            self._config(max_tokens="512", temperature="0.2", timeout="45"),
            LOGGER,
        )

        kwargs = self.attack.call_args.kwargs
        self.assertEqual(kwargs["target_max_tokens"], 512)
        self.assertEqual(kwargs["target_temperature"], 0.2)
        self.assertEqual(kwargs["target_timeout"], 45)

    def test_inline_judge_is_wired_when_ctx_judge_is_present(self):
        from hackagent.attacks._lib.inline_judge import CtxJudgeAdapter
        from tests.fakes.judge import FakeJudge

        port = FakeJudge(score=10.0, success=True)
        execute(
            ["g"],
            _router(),
            self._config(judges=[{"identifier": "j"}], _judge=port, _client=MagicMock()),
            LOGGER,
        )

        step_judge = self.attack.call_args.kwargs["step_judge"]
        self.assertIsInstance(step_judge, CtxJudgeAdapter)
        self.assertTrue(step_judge.available)
        self.assertIs(step_judge._judge, port)

    def test_unavailable_judge_is_dropped(self):
        judge = MagicMock()
        judge.available = False

        with patch.object(papgen, "_StepJudge", return_value=judge):
            execute(
                ["g"],
                _router(),
                self._config(judges=[{"identifier": "j"}], _client=MagicMock()),
                LOGGER,
            )

        self.assertIsNone(self.attack.call_args.kwargs["step_judge"])

    def test_result_id_is_injected_from_the_tracker(self):
        tracker = MagicMock()
        tracker.get_goal_context.return_value = SimpleNamespace(result_id="res-3")

        results = execute(["g"], _router(), self._config(_tracker=tracker), LOGGER)

        self.assertEqual(results[0]["result_id"], "res-3")

    def test_attacker_is_built_without_a_storage_backend(self):
        execute(["g"], _router(), {"attacker": {"identifier": "m"}}, LOGGER)

        self.create_attacker.assert_called_once_with({"identifier": "m"})


if __name__ == "__main__":
    unittest.main()
