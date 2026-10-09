# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""``connect`` builds a native :class:`Model` from a :class:`ModelSpec`.

No network I/O happens, so these construct real models and inspect their type
and wiring without reaching any provider.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from hackagent.core.contracts import AgentType, ModelSpec
from hackagent.models.completions import ClaudeCodeModel, LiteLLMModel, WebModel
from hackagent.models.connect import check_supported, connect
from hackagent.models.model import Model


class TestCheckSupported(unittest.TestCase):
    def test_accepts_providers_and_native_types(self):
        for agent_type in (
            AgentType.OPENAI_SDK,
            AgentType.OLLAMA,
            AgentType.CLAUDE_CODE,
            AgentType.GOOGLE_ADK,
            AgentType.WEB,
        ):
            check_supported(agent_type)  # no raise

    def test_rejects_unsupported_type(self):
        with self.assertRaisesRegex(ValueError, "Unsupported agent type"):
            check_supported(AgentType.MCP)


class TestConnectProvider(unittest.TestCase):
    def test_openai_sdk_builds_a_litellm_model(self):
        model = connect(
            ModelSpec(
                identifier="gpt-4",
                agent_type=AgentType.OPENAI_SDK,
                endpoint="http://localhost:8000/v1",
            )
        )
        self.assertIsInstance(model, LiteLLMModel)
        self.assertIsInstance(model, Model)

    def test_generation_knobs_are_carried(self):
        with patch("hackagent.models.connect.build_model") as build:
            connect(
                ModelSpec(
                    identifier="gpt-4",
                    agent_type=AgentType.OPENAI_SDK,
                    max_tokens=128,
                    temperature=0.5,
                    extra={"seed": 7, "unknown_knob": "dropped"},
                )
            )
            config = build.call_args.args[0]
            self.assertEqual(config.generation.max_tokens, 128)
            self.assertEqual(config.generation.temperature, 0.5)
            self.assertEqual(config.generation.seed, 7)

    def test_instance_id_is_accepted_and_ignored(self):
        model = connect(
            ModelSpec(identifier="gpt-4", agent_type=AgentType.OPENAI_SDK),
            instance_id="abc",
        )
        self.assertIsInstance(model, LiteLLMModel)


class TestConnectNative(unittest.TestCase):
    def test_native_types_are_built_directly_from_the_spec(self):
        with patch(
            "hackagent.models.completions.cli.shutil.which",
            return_value="/usr/bin/claude",
        ):
            model = connect(
                ModelSpec(identifier="sonnet", agent_type=AgentType.CLAUDE_CODE)
            )
        self.assertIsInstance(model, ClaudeCodeModel)

    def test_native_extra_options_survive(self):
        # ``url`` lives in spec.extra and must reach the WebModel — the detail a
        # spec→config projection would drop.
        model = connect(
            ModelSpec(
                identifier="site",
                agent_type=AgentType.WEB,
                endpoint="https://x.it/chat",
                extra={"input_selector": "textarea.prompt"},
            )
        )
        self.assertIsInstance(model, WebModel)
        self.assertEqual(model.input_selector, "textarea.prompt")

    def test_unsupported_type_raises(self):
        with self.assertRaisesRegex(ValueError, "Unsupported agent type"):
            connect(ModelSpec(identifier="x", agent_type=AgentType.MCP))


if __name__ == "__main__":
    unittest.main()
