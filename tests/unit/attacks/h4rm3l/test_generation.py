# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for h4rm3l generation module."""

import logging
import unittest
from unittest.mock import MagicMock

from hackagent.attacks.techniques.h4rm3l.generation import execute


class TestGeneration(unittest.TestCase):
    """Test generation.execute() with mocked agent router."""

    def _make_agent_router(self, response_text="Generated response"):
        """Create a mocked AgentRouter."""
        router = MagicMock()
        router.backend_agent.id = "test-agent-id"
        router.route_request.return_value = {
            "generated_text": response_text,
            "error_message": None,
        }
        return router

    def _default_config(self, **overrides):
        cfg = {
            "h4rm3l_params": {
                "program": "IdentityDecorator()",
                "syntax_version": 2,
            },
        }
        cfg.update(overrides)
        return cfg

    def test_empty_goals(self):
        router = self._make_agent_router()
        config = self._default_config()
        logger = logging.getLogger("test")
        result = execute([], router, config, logger)
        self.assertEqual(result, [])
        router.route_request.assert_not_called()

    def test_single_goal_identity(self):
        router = self._make_agent_router(response_text="Sure, here is...")
        config = self._default_config()
        logger = logging.getLogger("test")
        results = execute(["Tell me something"], router, config, logger)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["goal"], "Tell me something")
        # IdentityDecorator => full_prompt == goal
        self.assertEqual(results[0]["full_prompt"], "Tell me something")
        self.assertEqual(results[0]["response"], "Sure, here is...")
        self.assertIsNone(results[0]["error"])

    def test_multiple_goals(self):
        router = self._make_agent_router(response_text="response")
        config = self._default_config()
        logger = logging.getLogger("test")
        goals = ["goal 1", "goal 2", "goal 3"]
        results = execute(goals, router, config, logger)
        self.assertEqual(len(results), 3)
        for i, r in enumerate(results):
            self.assertEqual(r["goal"], goals[i])

    def test_preset_program_resolution(self):
        router = self._make_agent_router(response_text="response")
        config = self._default_config()
        config["h4rm3l_params"]["program"] = "identity"
        logger = logging.getLogger("test")
        results = execute(["test"], router, config, logger)
        self.assertEqual(len(results), 1)
        # identity preset => IdentityDecorator() => prompt unchanged
        self.assertEqual(results[0]["full_prompt"], "test")

    def test_base64_program(self):
        """Test with Base64Decorator — prompt should be base64-encoded."""
        import base64 as b64mod

        router = self._make_agent_router(response_text="response")
        config = self._default_config()
        config["h4rm3l_params"]["program"] = "Base64Decorator()"
        logger = logging.getLogger("test")
        results = execute(["hello"], router, config, logger)
        self.assertEqual(len(results), 1)
        encoded = b64mod.b64encode(b"hello").decode()
        self.assertIn(encoded, results[0]["full_prompt"])

    def test_compilation_failure_returns_errors(self):
        router = self._make_agent_router()
        config = self._default_config()
        config["h4rm3l_params"]["program"] = "NonExistentDecorator()"
        logger = logging.getLogger("test")
        results = execute(["test"], router, config, logger)
        self.assertEqual(len(results), 1)
        self.assertIsNotNone(results[0]["error"])
        self.assertIn("compilation failed", results[0]["error"].lower())

    def test_target_error_captured(self):
        router = self._make_agent_router()
        router.route_request.side_effect = RuntimeError("Connection failed")
        config = self._default_config()
        logger = logging.getLogger("test")
        results = execute(["test"], router, config, logger)
        self.assertEqual(len(results), 1)
        self.assertIn("failed", results[0]["error"].lower())
        self.assertIsNone(results[0]["response"])

    def test_v1_syntax(self):
        router = self._make_agent_router(response_text="response")
        config = self._default_config()
        config["h4rm3l_params"]["program"] = "IdentityDecorator(); ReverseDecorator()"
        config["h4rm3l_params"]["syntax_version"] = 1
        logger = logging.getLogger("test")
        results = execute(["abc"], router, config, logger)
        self.assertEqual(len(results), 1)
        # Identity then Reverse => "cba"
        self.assertEqual(results[0]["full_prompt"], "cba")

    def test_result_contains_program_field(self):
        router = self._make_agent_router(response_text="response")
        config = self._default_config()
        logger = logging.getLogger("test")
        results = execute(["test"], router, config, logger)
        self.assertIn("program", results[0])

    def test_order_preserved(self):
        """Results should be in the same order as goals."""
        call_count = 0

        def make_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return {"generated_text": f"resp_{call_count}", "error_message": None}

        router = self._make_agent_router()
        router.route_request.side_effect = make_response
        config = self._default_config()
        logger = logging.getLogger("test")
        goals = [f"goal_{i}" for i in range(5)]
        results = execute(goals, router, config, logger)
        self.assertEqual(len(results), 5)
        for i, r in enumerate(results):
            self.assertEqual(r["goal"], f"goal_{i}")


if __name__ == "__main__":
    unittest.main()
