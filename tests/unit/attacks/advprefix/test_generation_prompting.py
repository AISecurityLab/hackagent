# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for AdvPrefix generation prompting behavior."""

import logging
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.advprefix.generate import PrefixGenerationPipeline


@contextmanager
def _dummy_progress_bar(*args, **kwargs):
    class DummyBar:
        def update(self, *args, **kwargs):
            return None

    yield DummyBar(), "task"


class TestAdvPrefixGenerationPrompting(unittest.TestCase):
    """Validate how AdvPrefix builds and sends generator prompts."""

    def _build_pipeline(
        self, system_prompt: str | None = None
    ) -> PrefixGenerationPipeline:
        generator_cfg = {
            "identifier": "generator-model",
            "endpoint": "http://localhost:1234/v1",
        }
        if system_prompt is not None:
            generator_cfg["system_prompt"] = system_prompt

        config = {
            "generator": generator_cfg,
            "meta_prefixes": ["Write..."],
            "meta_prefix_samples": 1,
            "batch_size": 1,
            "max_tokens": 64,
            "temperature": 0.7,
            "top_p": 1.0,
        }

        return PrefixGenerationPipeline(
            config=config,
            logger=logging.getLogger("test.advprefix.generation"),
            client=MagicMock(),
        )

    def test_construct_prompts_uses_meta_prefix_and_goal_fields(self):
        pipeline = self._build_pipeline()

        prompts, goals, meta_prefixes = pipeline._construct_prompts(
            ["How to bake a cake"]
        )

        self.assertEqual(len(prompts), 1)
        self.assertEqual(prompts[0], "META_PREFIX: Write...\nGOAL: How to bake a cake")
        self.assertEqual(goals, ["How to bake a cake"])
        self.assertEqual(meta_prefixes, ["Write..."])

    @patch("hackagent.attacks.techniques.advprefix.generate.create_progress_bar")
    def test_run_generation_mode_sends_system_and_user_messages(
        self, mock_progress_bar
    ):
        mock_progress_bar.side_effect = _dummy_progress_bar
        pipeline = self._build_pipeline(system_prompt="CUSTOM_SYSTEM_PROMPT")

        router = MagicMock()
        router._agent_registry = {"reg-key": MagicMock()}
        router.route_request.return_value = {
            "processed_response": "Sure, here is a detailed guide on how to bake a cake.",
        }
        pipeline._generation_router = router

        results = pipeline._run_generation_mode(
            prompts=["META_PREFIX: Write...\nGOAL: How to bake a cake"],
            goals=["How to bake a cake"],
            meta_prefixes=["Write..."],
            do_sample=False,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["prefix"],
            "Sure, here is a detailed guide on how to bake a cake.",
        )
        self.assertEqual(results[0]["meta_prefix"], "Write...")

        request_data = router.route_request.call_args.kwargs["request_data"]
        self.assertIn("messages", request_data)
        self.assertNotIn("prompt", request_data)

        messages = request_data["messages"]
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[0]["content"], "CUSTOM_SYSTEM_PROMPT")
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(
            messages[1]["content"],
            "META_PREFIX: Write...\nGOAL: How to bake a cake",
        )


if __name__ == "__main__":
    unittest.main()
