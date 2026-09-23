# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for FC-Attack / tFC-Attack generation."""

import logging
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.fc import generation as fcgen
from hackagent.attacks.techniques.fc.generation import (
    _build_multimodal_messages,
    _build_text_only_messages,
    _build_text_only_prompt,
    _create_step_generator_router,
    _decompose_goal_to_steps,
    _generate_steps_with_model,
    _get_steps,
    _parse_steps_from_response,
    _send_to_target,
    execute_fc,
    execute_tfc,
)
from hackagent.attacks.techniques.fc.prompts import SYSTEM_PROMPT, USER_PROMPT

LOGGER = logging.getLogger("test.fc.generation")
LOGGER.addHandler(logging.NullHandler())


def _victim_router(response=None, side_effect=None):
    router = MagicMock()
    router.backend_agent = SimpleNamespace(id="victim-id")
    if side_effect is not None:
        router.route_request.side_effect = side_effect
    else:
        router.route_request.return_value = response or {"generated_text": "answer"}
    return router


class TestDecomposeGoalToSteps(unittest.TestCase):
    def test_sentences_are_used_when_there_are_enough(self):
        steps = _decompose_goal_to_steps("first thing. second thing; third thing", 2)

        self.assertEqual(steps, ["first thing", "second thing"])

    def test_very_short_goals_use_the_scaffold_template(self):
        steps = _decompose_goal_to_steps("do it", 5)

        self.assertEqual(len(steps), 5)
        self.assertIn("Understand the task", steps[0])
        self.assertIn("do it", steps[0])

    def test_short_goal_scaffold_is_truncated_to_num_steps(self):
        steps = _decompose_goal_to_steps("do it", 2)

        self.assertEqual(len(steps), 2)

    def test_long_goals_are_chunked_into_the_requested_number_of_steps(self):
        goal = " ".join(f"word{i}" for i in range(12))

        steps = _decompose_goal_to_steps(goal, 4)

        self.assertEqual(len(steps), 4)
        self.assertEqual(" ".join(steps), goal)

    def test_padding_keeps_the_step_count(self):
        steps = _decompose_goal_to_steps("alpha beta gamma delta", 6)

        self.assertEqual(len(steps), 6)
        self.assertIn("Continue with remaining details...", steps)


class TestParseStepsFromResponse(unittest.TestCase):
    def test_numbered_lines_are_unwrapped(self):
        steps = _parse_steps_from_response("1. first\n2) second\n3. third", 3)

        self.assertEqual(steps, ["first", "second", "third"])

    def test_unnumbered_lines_are_kept_and_headings_dropped(self):
        steps = _parse_steps_from_response("# Heading\nplain line\n\nanother", 5)

        self.assertEqual(steps, ["plain line", "another"])

    def test_output_is_capped(self):
        steps = _parse_steps_from_response("\n".join(f"{i}. s{i}" for i in range(9)), 3)

        self.assertEqual(len(steps), 3)

    def test_empty_response_falls_back_to_heuristic_decomposition(self):
        steps = _parse_steps_from_response("   ", 3)

        self.assertEqual(len(steps), 3)

    def test_heading_only_response_falls_back_to_heuristic_decomposition(self):
        steps = _parse_steps_from_response("   \n# only a heading", 3)

        self.assertEqual(len(steps), 3)
        self.assertTrue(
            any("heading" in step.lower() or "Understand" in step for step in steps)
        )


class TestCreateStepGeneratorRouter(unittest.TestCase):
    def test_absent_configuration_returns_none(self):
        self.assertIsNone(_create_step_generator_router(_victim_router(), {}, LOGGER))

    def test_non_dict_configuration_returns_none(self):
        self.assertIsNone(
            _create_step_generator_router(
                _victim_router(), {"step_generator": "gpt"}, LOGGER
            )
        )

    def test_missing_identifier_returns_none(self):
        self.assertIsNone(
            _create_step_generator_router(
                _victim_router(), {"step_generator": {"endpoint": "http://x"}}, LOGGER
            )
        )

    def test_router_is_created_from_the_generator_block(self):
        agent_router = _victim_router()
        generator = MagicMock()

        with patch(
            "hackagent.attacks.shared.llm_router.connect_role",
            return_value=(generator, "gen-key"),
        ) as factory:
            result = _create_step_generator_router(
                agent_router,
                {
                    "step_generator": {
                        "identifier": "gen-model",
                        "endpoint": "http://gen",
                        "max_tokens": "256",
                        "temperature": "0.5",
                    }
                },
                LOGGER,
            )

        router, key, cfg = result
        self.assertIs(router, generator)
        self.assertEqual(key, "gen-key")
        self.assertEqual(cfg["identifier"], "gen-model")
        passed = factory.call_args.args[0]
        self.assertEqual(passed["max_tokens"], 256)
        self.assertEqual(passed["temperature"], 0.5)
        self.assertEqual(passed["agent_type"], "OPENAI_SDK")


class TestGenerateStepsWithModel(unittest.TestCase):
    def test_model_output_is_parsed_into_steps(self):
        router = _victim_router({"generated_text": "1. alpha\n2. beta"})

        steps = _generate_steps_with_model(
            "goal", 2, router, "key", {"max_tokens": 128, "temperature": 0.1}, LOGGER
        )

        self.assertEqual(steps, ["alpha", "beta"])
        request = router.route_request.call_args.kwargs["request_data"]
        self.assertEqual(request["max_tokens"], 128)
        self.assertEqual(request["temperature"], 0.1)

    def test_empty_output_returns_none(self):
        router = _victim_router({"generated_text": ""})

        self.assertIsNone(
            _generate_steps_with_model("goal", 2, router, "key", {}, LOGGER)
        )

    def test_router_failure_is_swallowed(self):
        router = _victim_router(side_effect=RuntimeError("offline"))
        logger = MagicMock()

        self.assertIsNone(
            _generate_steps_with_model("goal", 2, router, "key", {}, logger)
        )
        logger.warning.assert_called_once()


class TestGetSteps(unittest.TestCase):
    def test_heuristic_decomposition_without_a_generator(self):
        steps = _get_steps("alpha. beta. gamma", 3, False, None, LOGGER)

        self.assertEqual(steps, ["alpha", "beta", "gamma"])

    def test_generator_output_is_preferred(self):
        router = _victim_router({"generated_text": "1. from model"})

        steps = _get_steps("goal", 1, False, (router, "k", {}), LOGGER)

        self.assertEqual(steps, ["from model"])

    def test_generator_failure_falls_back_to_the_heuristic(self):
        router = _victim_router({"generated_text": ""})

        steps = _get_steps("alpha. beta", 2, False, (router, "k", {}), LOGGER)

        self.assertEqual(steps, ["alpha", "beta"])

    def test_last_step_truncation_keeps_a_minimum_length(self):
        steps = _get_steps("alpha. bcdefghij", 2, True, None, LOGGER)

        self.assertTrue(steps[-1].endswith("..."))
        self.assertEqual(steps[-1], "bcdef...")

    def test_truncation_of_a_very_short_step(self):
        steps = _get_steps("alpha. bc", 2, True, None, LOGGER)

        self.assertEqual(steps[-1], "bc...")


class TestMessageBuilders(unittest.TestCase):
    def test_multimodal_messages_carry_image_and_text_parts(self):
        messages = _build_multimodal_messages("data:image/png;base64,AAA", "sys", "usr")

        self.assertEqual(messages[0], {"role": "system", "content": "sys"})
        content = messages[1]["content"]
        self.assertEqual(content[0]["image_url"]["url"], "data:image/png;base64,AAA")
        self.assertEqual(content[1]["text"], "usr")

    def test_multimodal_messages_omit_an_empty_system_prompt(self):
        messages = _build_multimodal_messages("url", "", "usr")

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "user")

    def test_text_prompt_uses_the_language_hint_for_the_format(self):
        prompt = _build_text_only_prompt("digraph {}", "tikz")

        self.assertIn("```latex", prompt)
        self.assertIn("digraph {}", prompt)

    def test_unknown_format_is_used_verbatim_as_the_hint(self):
        prompt = _build_text_only_prompt("graph", "graphviz")

        self.assertIn("```graphviz", prompt)

    def test_ascii_format_has_no_language_hint(self):
        prompt = _build_text_only_prompt("+--+", "ascii")

        self.assertIn("```\n+--+", prompt)

    def test_text_only_messages_embed_the_graph(self):
        messages = _build_text_only_messages("digraph {}", "dot", "sys")

        self.assertEqual(messages[0]["content"], "sys")
        self.assertIn("digraph {}", messages[1]["content"])

    def test_text_only_messages_omit_an_empty_system_prompt(self):
        messages = _build_text_only_messages("g", "dot", "")

        self.assertEqual(len(messages), 1)


class TestSendToTarget(unittest.TestCase):
    def test_response_text_and_elapsed_time_are_returned(self):
        router = _victim_router({"generated_text": "the answer"})

        text, error, elapsed = _send_to_target(
            [{"role": "user", "content": "hi"}],
            router,
            "victim-id",
            {"max_tokens": 64},
            LOGGER,
            1,
            1,
        )

        self.assertEqual(text, "the answer")
        self.assertIsNone(error)
        self.assertGreaterEqual(elapsed, 0.0)
        self.assertEqual(
            router.route_request.call_args.kwargs["request_data"]["max_tokens"], 64
        )

    def test_max_tokens_is_omitted_when_unset(self):
        router = _victim_router()

        _send_to_target([], router, "victim-id", {}, LOGGER, 1, 1)

        self.assertNotIn(
            "max_tokens", router.route_request.call_args.kwargs["request_data"]
        )

    def test_error_responses_are_surfaced(self):
        router = _victim_router({"error_message": "bad gateway"})
        logger = MagicMock()

        text, error, _ = _send_to_target([], router, "v", {}, logger, 1, 1)

        self.assertIsNone(text)
        self.assertEqual(error, "bad gateway")
        logger.warning.assert_called_once()


class TestExecuteFc(unittest.TestCase):
    def setUp(self):
        self.render_patch = patch.object(
            fcgen,
            "render_flowchart",
            return_value={"image_data_url": "data:image/png;base64,IMG"},
        )
        self.render = self.render_patch.start()
        self.addCleanup(self.render_patch.stop)

    def test_results_carry_the_rendered_flowchart_and_response(self):
        router = _victim_router({"generated_text": "the answer"})

        results = execute_fc(["goal one"], router, {}, LOGGER)

        self.assertEqual(len(results), 1)
        row = results[0]
        self.assertEqual(row["goal"], "goal one")
        self.assertEqual(row["layout"], "vertical")
        self.assertEqual(row["image_data_url"], "data:image/png;base64,IMG")
        self.assertEqual(row["response"], "the answer")
        self.assertEqual(row["text_prompt"], USER_PROMPT)
        self.assertIn("generation_elapsed_s", row)

    def test_layout_and_step_parameters_reach_the_renderer(self):
        router = _victim_router()

        execute_fc(
            ["goal"],
            router,
            {"fc_params": {"layout": "tortuous", "dpi": 100, "num_steps": 3}},
            LOGGER,
        )

        kwargs = self.render.call_args.kwargs
        self.assertEqual(kwargs["layout"], "tortuous")
        self.assertEqual(kwargs["dpi"], 100)
        self.assertEqual(len(kwargs["steps"]), 3)

    def test_multimodal_message_is_sent_to_the_victim(self):
        router = _victim_router()

        execute_fc(["goal"], router, {}, LOGGER)

        messages = router.route_request.call_args.kwargs["request_data"]["messages"]
        self.assertEqual(messages[0]["content"], SYSTEM_PROMPT)
        self.assertEqual(
            messages[1]["content"][0]["image_url"]["url"], "data:image/png;base64,IMG"
        )

    def test_rendering_failure_is_recorded_per_goal(self):
        self.render.side_effect = RuntimeError("graphviz missing")
        router = _victim_router()

        results = execute_fc(["goal"], router, {}, LOGGER)

        self.assertIn("Rendering failed", results[0]["error"])
        self.assertIsNone(results[0]["response"])
        router.route_request.assert_not_called()

    def test_target_failure_is_recorded_per_goal(self):
        router = _victim_router(side_effect=RuntimeError("timeout"))

        results = execute_fc(["goal"], router, {}, LOGGER)

        self.assertIn("Execution failed", results[0]["error"])
        self.assertIsNone(results[0]["response"])

    def test_results_preserve_goal_order(self):
        router = _victim_router(
            side_effect=lambda registration_key, request_data: {"generated_text": "ok"}
        )

        results = execute_fc(["g0", "g1", "g2"], router, {}, LOGGER)

        self.assertEqual([r["goal"] for r in results], ["g0", "g1", "g2"])

    def test_tracker_receives_an_interaction_trace(self):
        router = _victim_router()
        tracker = MagicMock()
        tracker.get_goal_context_by_goal.return_value = SimpleNamespace(
            result_id="res-1"
        )

        results = execute_fc(["goal"], router, {"_tracker": tracker}, LOGGER)

        tracker.add_interaction_trace.assert_called_once()
        trace = tracker.add_interaction_trace.call_args.kwargs
        self.assertEqual(trace["step_name"], "FC-Attack Generation (vertical)")
        self.assertEqual(
            trace["metadata"]["image_data_url"], "data:image/png;base64,IMG"
        )
        self.assertEqual(results[0]["result_id"], "res-1")

    def test_untracked_goals_do_not_get_a_result_id(self):
        router = _victim_router()
        tracker = MagicMock()
        tracker.get_goal_context_by_goal.return_value = None

        results = execute_fc(["goal"], router, {"_tracker": tracker}, LOGGER)

        tracker.add_interaction_trace.assert_not_called()
        self.assertNotIn("result_id", results[0])


class TestExecuteTfc(unittest.TestCase):
    def test_graph_text_is_serialised_in_the_configured_format(self):
        router = _victim_router({"generated_text": "answer"})

        results = execute_tfc(
            ["goal"], router, {"tfc_params": {"text_format": "mermaid"}}, LOGGER
        )

        row = results[0]
        self.assertEqual(row["text_format"], "mermaid")
        self.assertIn("flowchart", row["graph_text"].lower())
        self.assertIn("```mermaid", row["full_prompt"])
        self.assertEqual(row["response"], "answer")

    def test_unknown_format_falls_back_to_dot(self):
        router = _victim_router()
        logger = MagicMock()

        results = execute_tfc(
            ["goal"], router, {"tfc_params": {"text_format": "svg"}}, logger
        )

        logger.error.assert_called_once()
        self.assertIn("digraph", results[0]["graph_text"])

    def test_text_only_message_is_sent_to_the_victim(self):
        router = _victim_router()

        execute_tfc(["goal"], router, {}, LOGGER)

        messages = router.route_request.call_args.kwargs["request_data"]["messages"]
        self.assertEqual(messages[0]["content"], SYSTEM_PROMPT)
        self.assertIsInstance(messages[1]["content"], str)

    def test_target_failure_is_recorded_per_goal(self):
        router = _victim_router(side_effect=RuntimeError("timeout"))

        results = execute_tfc(["goal"], router, {}, LOGGER)

        self.assertIn("Execution failed", results[0]["error"])

    def test_results_preserve_goal_order(self):
        router = _victim_router()

        results = execute_tfc(["g0", "g1"], router, {}, LOGGER)

        self.assertEqual([r["goal"] for r in results], ["g0", "g1"])

    def test_tracker_receives_an_interaction_trace(self):
        router = _victim_router()
        tracker = MagicMock()
        tracker.get_goal_context_by_goal.return_value = SimpleNamespace(
            result_id="res-2"
        )

        results = execute_tfc(["goal"], router, {"_tracker": tracker}, LOGGER)

        trace = tracker.add_interaction_trace.call_args.kwargs
        self.assertEqual(trace["step_name"], "tFC-Attack Generation (vertical)")
        self.assertIn("graph_text", trace["metadata"])
        self.assertEqual(results[0]["result_id"], "res-2")


if __name__ == "__main__":
    unittest.main()
