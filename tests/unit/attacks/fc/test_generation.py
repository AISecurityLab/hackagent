# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for FC-Attack step decomposition and generator-router setup."""

import logging
import unittest
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.fc.generation import (
    _create_step_generator_router,
    _decompose_goal_to_steps,
    _parse_steps_from_response,
)


def _logger() -> logging.Logger:
    logger = logging.getLogger("test.fc.generation")
    logger.disabled = True
    return logger


class TestDecomposeGoalToSteps(unittest.TestCase):
    def test_splits_sentences_when_enough_are_present(self):
        goal = "Research the target. Gather tools. Execute the plan. Verify the result."
        steps = _decompose_goal_to_steps(goal, 3)
        self.assertEqual(
            steps,
            ["Research the target", "Gather tools", "Execute the plan"],
        )

    def test_short_goal_uses_templated_steps(self):
        steps = _decompose_goal_to_steps("hack", 4)
        self.assertEqual(len(steps), 4)
        self.assertTrue(steps[0].startswith("Understand the task:"))
        self.assertIn("hack", steps[1])

    def test_long_goal_chunks_words(self):
        goal = "write a detailed guide for bypassing the content filter using roleplay"
        steps = _decompose_goal_to_steps(goal, 3)
        self.assertEqual(len(steps), 3)
        self.assertEqual(" ".join(steps).split(), goal.split())

    def test_pads_when_chunks_are_insufficient(self):
        # More than 3 words avoids the short-goal templates; asking for more
        # steps than words forces the remainder padding branch.
        steps = _decompose_goal_to_steps("alpha bravo charlie delta", 6)
        self.assertEqual(len(steps), 6)
        self.assertEqual(steps[-1], "Continue with remaining details...")


class TestParseStepsFromResponse(unittest.TestCase):
    def test_parses_numbered_steps(self):
        text = "1. Open the app\n2) Enter the payload\n3. Submit the form"
        self.assertEqual(
            _parse_steps_from_response(text, 2),
            ["Open the app", "Enter the payload"],
        )

    def test_keeps_unnumbered_content_lines(self):
        text = "# heading\nDo the first thing\nThen do the second"
        self.assertEqual(
            _parse_steps_from_response(text, 2),
            ["Do the first thing", "Then do the second"],
        )

    def test_falls_back_to_heuristic_when_empty(self):
        steps = _parse_steps_from_response("   \n# only a heading", 3)
        self.assertEqual(len(steps), 3)
        self.assertTrue(
            any("heading" in step.lower() or "Understand" in step for step in steps)
        )


class TestCreateStepGeneratorRouter(unittest.TestCase):
    def test_returns_none_without_step_generator_config(self):
        router = MagicMock()
        self.assertIsNone(_create_step_generator_router(router, {}, _logger()))
        self.assertIsNone(
            _create_step_generator_router(router, {"step_generator": "x"}, _logger())
        )
        self.assertIsNone(
            _create_step_generator_router(
                router, {"step_generator": {"endpoint": "http://x"}}, _logger()
            )
        )

    def test_creates_router_when_identifier_is_present(self):
        agent_router = MagicMock()
        agent_router.backend = MagicMock()
        created = (MagicMock(), "reg-key")
        with patch(
            "hackagent.attacks.shared.router_factory.create_router",
            return_value=created,
        ) as mock_create:
            result = _create_step_generator_router(
                agent_router,
                {
                    "step_generator": {
                        "identifier": "ollama/llama3",
                        "endpoint": "http://localhost:11434",
                        "max_tokens": "128",
                    }
                },
                _logger(),
            )
        self.assertEqual(result[0], created[0])
        self.assertEqual(result[1], "reg-key")
        self.assertEqual(result[2]["identifier"], "ollama/llama3")
        config = mock_create.call_args.kwargs["config"]
        self.assertEqual(config["identifier"], "ollama/llama3")
        self.assertEqual(config["max_tokens"], 128)
        self.assertEqual(config["agent_type"], "OPENAI_SDK")


if __name__ == "__main__":
    unittest.main()
