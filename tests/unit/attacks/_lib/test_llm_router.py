# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the route_request surface over an LLM."""

import asyncio
from types import SimpleNamespace

import pytest

from hackagent.attacks._lib.llm_router import LLMRouter, connect_role
from hackagent.core.contracts import AgentType
from tests.fakes import FakeLLM, in_memory_store


class TestLLMRouter:
    def test_route_request_sends_to_the_llm(self):
        llm = FakeLLM(["hi"])
        router = LLMRouter(llm)

        response = router.route_request(
            registration_key=router.registration_key, request_data={"prompt": "x"}
        )

        assert response["generated_text"] == "hi"
        assert llm.requests == [{"prompt": "x"}]

    def test_unknown_registration_key_returns_404_envelope(self):
        router = LLMRouter(FakeLLM())
        response = router.route_request("nonexistent-key", {"prompt": "hi"})
        assert response["status_code"] == 404
        assert response["raw_response_status"] == 404
        assert "Agent not found" in response["error_message"]

    def test_async_route_request(self):
        router = LLMRouter(FakeLLM(["async"]))
        response = asyncio.run(
            router.route_request_async(router.registration_key, {"prompt": "x"})
        )
        assert response["generated_text"] == "async"

    def test_identity_defaults_to_the_spec(self):
        router = LLMRouter(FakeLLM(instance_id="k1"))
        assert router.backend_agent.id == "k1"
        assert router.backend_agent.name == "fake-model"
        assert router.backend_agent.agent_type == AgentType.OPENAI_SDK.value
        assert list(router._agent_registry) == ["k1"]
        assert router.get_agent_instance("k1") is router.llm.adapter

    def test_explicit_agent_record_is_exposed(self):
        record = SimpleNamespace(id="rec-1", name="target", agent_type="OLLAMA")
        router = LLMRouter(FakeLLM(instance_id="rec-1"), agent=record)
        assert router.backend_agent is record

    def test_with_params_scopes_requests_and_keeps_identity(self):
        llm = FakeLLM()
        router = LLMRouter(llm, agent=SimpleNamespace(id=llm.instance_id))
        scoped = router.with_params(max_tokens=64)

        scoped.route_request(scoped.registration_key, {"prompt": "a"})
        router.route_request(router.registration_key, {"prompt": "b"})

        assert scoped.backend_agent is router.backend_agent
        assert llm.requests == [{"max_tokens": 64, "prompt": "a"}, {"prompt": "b"}]


class TestConnectRole:
    def test_connects_without_touching_storage(self):
        store = in_memory_store()
        router, key = connect_role(
            {
                "identifier": "llama3",
                "endpoint": "http://localhost:11434",
                "agent_type": "OLLAMA",
            },
            name="attacker",
        )
        assert key == router.registration_key
        assert router.backend_agent.name == "llama3"
        assert store.list_agents().items == []

    def test_invalid_config_raises(self):
        with pytest.raises(ValueError):
            connect_role({"endpoint": "http://x"})
