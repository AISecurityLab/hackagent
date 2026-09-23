# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for role-model specs and the ModelFactory."""

from unittest.mock import patch

import pytest

from hackagent.core.contracts import AgentType, ModelSpec
from hackagent.core.settings import Settings
from hackagent.models.dispatch import adapter_config
from hackagent.models.factory import ModelFactory, passthrough_params, spec_from_config
from hackagent.models.guardrail import GuardrailSpec


@pytest.fixture
def basic_config():
    return {
        "identifier": "test-model",
        "endpoint": "https://api.example.com/v1",
        "agent_type": "OPENAI_SDK",
        "max_tokens": 500,
        "temperature": 0.7,
        "agent_metadata": {},
    }


def _settings(api_key=None, base_url="https://api.hackagent.dev"):
    return Settings.resolve(
        api_key=api_key or "",
        base_url=base_url,
        env={},
        config_path="/nonexistent/hackagent/config.json",
    )


class TestSpecFromConfig:
    def test_basic_fields(self, basic_config):
        spec = spec_from_config(basic_config)
        assert spec.identifier == "test-model"
        assert spec.endpoint == "https://api.example.com/v1"
        assert spec.agent_type is AgentType.OPENAI_SDK
        assert spec.max_tokens == 500
        assert spec.temperature == 0.7
        assert spec.api_key is None

    def test_missing_identifier_raises(self):
        with pytest.raises(ValueError, match="identifier"):
            spec_from_config({"endpoint": "http://x"})

    def test_model_overrides_identifier(self, basic_config):
        basic_config["model"] = "real-model"
        assert spec_from_config(basic_config).identifier == "real-model"

    def test_request_timeout_is_accepted(self, basic_config):
        basic_config["request_timeout"] = 30
        assert spec_from_config(basic_config).timeout == 30

    def test_literal_api_key(self, basic_config):
        basic_config["api_key"] = "sk-literal"
        spec = spec_from_config(basic_config)
        assert spec.api_key == "sk-literal"
        assert spec.api_key_env is None

    def test_api_key_naming_a_set_env_var(self, basic_config):
        basic_config["api_key"] = "MY_API_KEY_VAR"
        with patch.dict("os.environ", {"MY_API_KEY_VAR": "env-value-123"}):
            spec = spec_from_config(basic_config)
            assert spec.api_key_env == "MY_API_KEY_VAR"
            assert adapter_config(spec)["api_key"] == "env-value-123"

    def test_api_key_from_agent_metadata(self, basic_config):
        basic_config["agent_metadata"] = {"api_key": "override-key"}
        assert spec_from_config(basic_config).api_key == "override-key"

    def test_invalid_agent_type_defaults_to_openai_sdk(self, basic_config):
        basic_config["agent_type"] = "INVALID_TYPE"
        assert spec_from_config(basic_config).agent_type is AgentType.OPENAI_SDK

    def test_default_agent_type_is_configurable(self):
        spec = spec_from_config(
            {"identifier": "m"}, default_agent_type=AgentType.OLLAMA
        )
        assert spec.agent_type is AgentType.OLLAMA

    def test_agent_type_aliases(self, basic_config):
        basic_config["agent_type"] = "openai"
        assert spec_from_config(basic_config).agent_type is AgentType.OPENAI_SDK

    def test_metadata_merged_into_extra(self, basic_config):
        basic_config["agent_metadata"] = {"custom_param": "value123"}
        spec = spec_from_config(basic_config)
        assert adapter_config(spec)["custom_param"] == "value123"

    def test_metadata_never_overrides_identity(self, basic_config):
        basic_config["agent_metadata"] = {"name": "other", "endpoint": "http://evil"}
        config = adapter_config(spec_from_config(basic_config))
        assert config["name"] == "test-model"
        assert config["endpoint"] == "https://api.example.com/v1"

    def test_top_level_extra_body_is_preserved(self, basic_config):
        basic_config["extra_body"] = {"reasoning": {"enabled": True}}
        config = adapter_config(spec_from_config(basic_config))
        assert config["extra_body"] == {"reasoning": {"enabled": True}}

    def test_no_reasoning_default_is_injected(self):
        for endpoint in (
            "https://api.hackagent.dev/v1",
            "https://openrouter.ai/api/v1",
        ):
            config = adapter_config(
                spec_from_config({"identifier": "judge", "endpoint": endpoint})
            )
            assert "extra_body" not in config

    def test_openai_request_options_are_passed_through(self, basic_config):
        basic_config.update(
            {
                "reasoning_effort": "minimal",
                "frequency_penalty": 0.2,
                "presence_penalty": 0.1,
                "seed": 42,
                "stop": ["END"],
                "response_format": {"type": "json_object"},
                "logit_bias": {"123": -100},
            }
        )
        config = adapter_config(spec_from_config(basic_config))
        assert config["reasoning_effort"] == "minimal"
        assert config["frequency_penalty"] == 0.2
        assert config["presence_penalty"] == 0.1
        assert config["seed"] == 42
        assert config["stop"] == ["END"]
        assert config["response_format"] == {"type": "json_object"}
        assert config["logit_bias"] == {"123": -100}

    def test_ollama_thinking_is_forwarded(self, basic_config):
        basic_config["agent_type"] = "OLLAMA"
        basic_config["thinking"] = False
        assert spec_from_config(basic_config).thinking is False

    def test_non_ollama_thinking_is_dropped(self, basic_config):
        basic_config["thinking"] = False
        spec = spec_from_config(basic_config)
        assert spec.thinking is None
        assert "thinking" not in adapter_config(spec)

    def test_spec_type_reads_its_own_fields(self, basic_config):
        basic_config["system_prompt"] = "classify"
        spec = spec_from_config(basic_config, spec_type=GuardrailSpec)
        assert isinstance(spec, GuardrailSpec)
        assert spec.system_prompt == "classify"

    def test_passthrough_params_skips_unset_values(self):
        assert passthrough_params({"seed": 1, "stop": None, "other": 2}) == {"seed": 1}


class TestModelFactoryCredentials:
    def test_storage_key_is_never_a_fallback_for_other_providers(self):
        factory = ModelFactory(_settings(api_key="ha-key"))
        spec = ModelSpec(identifier="gpt-4", endpoint="https://openrouter.ai/api/v1")
        assert factory.with_credentials(spec).api_key is None

    def test_gateway_spec_without_key_gets_the_gateway_key(self):
        factory = ModelFactory(_settings(api_key="ha-key"))
        spec = ModelSpec(identifier="judge", endpoint="https://api.hackagent.dev/v1")
        assert factory.with_credentials(spec).api_key == "ha-key"

    def test_gateway_spec_keeps_its_own_key(self):
        factory = ModelFactory(_settings(api_key="ha-key"))
        spec = ModelSpec(
            identifier="judge",
            endpoint="https://api.hackagent.dev/v1",
            api_key_env="MY_KEY",
        )
        assert factory.with_credentials(spec) is spec

    def test_local_mode_adds_nothing(self):
        factory = ModelFactory(_settings())
        spec = ModelSpec(identifier="judge", endpoint="https://api.hackagent.dev/v1")
        assert not factory.is_gateway(spec.endpoint)
        assert factory.with_credentials(spec).api_key is None

    def test_for_role_connects_without_storage(self):
        factory = ModelFactory(_settings(api_key="ha-key"))
        llm = factory.for_role(
            ModelSpec(identifier="judge", endpoint="https://api.hackagent.dev/v1")
        )
        assert llm.adapter.actual_api_key == "ha-key"
        assert llm.describe().api_key == "ha-key"
