# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Sanity checks for the multi-provider LiteLLM demo example."""

import logging
import os
import unittest
from unittest.mock import patch

from hackagent.examples.litellm_multi_provider.demo import (
    _PROVIDERS,
    build_demo_config,
)
from hackagent.router.types import AgentTypeEnum

logging.disable(logging.CRITICAL)


# Set fake credentials for the providers whose ``api_key_env`` is non-None
# so ``build_demo_config`` can run without exiting.
_FAKE_ENV = {
    settings["api_key_env"]: "test-key"
    for settings in _PROVIDERS.values()
    if settings["api_key_env"]
}


class TestProvidersTable(unittest.TestCase):
    def test_every_entry_has_required_fields(self):
        required = {"target_model", "attacker_model", "judge_model", "api_key_env"}
        for name, settings in _PROVIDERS.items():
            with self.subTest(provider=name):
                self.assertEqual(set(settings.keys()), required)

    def test_model_strings_carry_a_provider_prefix(self):
        """Each model string should start with a LiteLLM provider prefix."""
        for name, settings in _PROVIDERS.items():
            with self.subTest(provider=name):
                for key in ("target_model", "attacker_model", "judge_model"):
                    self.assertIn("/", settings[key], settings[key])

    def test_anthropic_provider_at_minimum(self):
        """Anthropic stays in the table — used as the default in the demo."""
        self.assertIn("anthropic", _PROVIDERS)


class TestBuildDemoConfig(unittest.TestCase):
    @patch.dict(os.environ, _FAKE_ENV, clear=False)
    def test_build_config_returns_litellm_agent_type(self):
        config = build_demo_config("anthropic")
        self.assertEqual(config["agent"]["agent_type"], AgentTypeEnum.LITELLM)
        self.assertTrue(
            config["agent"]["adapter_operational_config"]["name"].startswith(
                "anthropic/"
            )
        )
        # Attacker + judge also use LITELLM.
        self.assertEqual(
            config["attack_config"]["attacker"]["agent_type"],
            AgentTypeEnum.LITELLM,
        )
        self.assertEqual(
            config["attack_config"]["judge"]["agent_type"],
            AgentTypeEnum.LITELLM,
        )

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_api_key_env_exits(self):
        with self.assertRaises(SystemExit):
            build_demo_config("anthropic")

    def test_unknown_provider_exits(self):
        with self.assertRaises(SystemExit):
            build_demo_config("does-not-exist")

    @patch.dict(os.environ, {"AWS_REGION": "us-east-1"}, clear=False)
    def test_bedrock_does_not_require_api_key_env(self):
        """Bedrock authenticates via the standard AWS chain, not an env var."""
        config = build_demo_config("bedrock")
        # No ``api_key`` key in the adapter config since AWS handles auth.
        self.assertNotIn("api_key", config["agent"]["adapter_operational_config"])


if __name__ == "__main__":
    unittest.main()
