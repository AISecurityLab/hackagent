# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import unittest
import uuid
from unittest.mock import MagicMock, patch
from hackagent.server.storage.base import OrganizationContext
from hackagent.router.types import AgentTypeEnum
from hackagent.router.router import AgentRouter


def _make_context(org_id=None, user_id="test_user"):
    ctx = MagicMock(spec=OrganizationContext)
    ctx.org_id = org_id or uuid.uuid4()
    ctx.user_id = user_id
    return ctx


def _make_agent_rec(
    agent_id=None,
    name="TestAgent",
    agent_type_str="GOOGLE_ADK",
    endpoint="http://fake.com/",
    metadata=None,
    org_id=None,
):
    rec = MagicMock()
    rec.id = agent_id or uuid.uuid4()
    rec.name = name
    rec.agent_type = agent_type_str
    rec.endpoint = endpoint
    rec.metadata = metadata if metadata is not None else {}
    rec.organization = org_id or uuid.uuid4()
    rec.owner = "local"
    return rec


def _make_backend(org_id=None, user_id="test_user"):
    backend = MagicMock()
    backend.get_context.return_value = _make_context(org_id=org_id, user_id=user_id)
    backend.get_api_key.return_value = None
    return backend


class TestAgentRouterInitialization(unittest.TestCase):
    @patch("hackagent.router.router.LiteLLMAgent", autospec=True)
    @patch("hackagent.router.router.ADKAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_agent_router_init_creates_new_agent_if_not_exists(
        self,
        MockAgentMap,
        MockADKAdapter,
        MockLiteLLMAdapter,
    ):
        MockAgentMap[AgentTypeEnum.GOOGLE_ADK] = MockADKAdapter
        MockAgentMap[AgentTypeEnum.LITELLM] = MockLiteLLMAdapter
        MockADKAdapter.__name__ = "ADKAgent"
        MockLiteLLMAdapter.__name__ = "LiteLLMAgent"

        mock_org_id = uuid.uuid4()
        mock_backend = _make_backend(org_id=mock_org_id, user_id="123")
        mock_created_agent_id = uuid.uuid4()
        agent_name = "TestAgent"
        agent_endpoint = "http://fake-agent-endpoint.com/"
        agent_metadata = {"initial_meta": "value"}
        adapter_op_config = {"user_id": "test_user_from_op_config"}

        mock_backend.create_or_update_agent.return_value = _make_agent_rec(
            agent_id=mock_created_agent_id,
            name=agent_name,
            agent_type_str="GOOGLE_ADK",
            endpoint=agent_endpoint,
            metadata=agent_metadata,
            org_id=mock_org_id,
        )

        router = AgentRouter(
            backend=mock_backend,
            name=agent_name,
            agent_type=AgentTypeEnum.GOOGLE_ADK,
            endpoint=agent_endpoint,
            metadata=agent_metadata,
            adapter_operational_config=adapter_op_config,
            overwrite_metadata=True,
        )

        mock_backend.create_or_update_agent.assert_called_once_with(
            name=agent_name,
            agent_type=AgentTypeEnum.GOOGLE_ADK.value,
            endpoint=agent_endpoint,
            metadata=agent_metadata,
            overwrite_metadata=True,
        )

        MockADKAdapter.assert_called_once()
        mock_adk_instance = MockADKAdapter.return_value
        adapter_kwargs = MockADKAdapter.call_args[1]
        self.assertEqual(adapter_kwargs["id"], str(mock_created_agent_id))
        self.assertEqual(
            adapter_kwargs["config"],
            {
                "user_id": "test_user_from_op_config",
                "name": agent_name,
                "endpoint": agent_endpoint,
            },
        )
        MockLiteLLMAdapter.assert_not_called()
        self.assertEqual(router.backend, mock_backend)
        self.assertIsNotNone(router.backend_agent)
        self.assertEqual(router.backend_agent.id, mock_created_agent_id)
        self.assertIn(str(mock_created_agent_id), router._agent_registry)
        self.assertEqual(
            router._agent_registry[str(mock_created_agent_id)], mock_adk_instance
        )

    @patch("hackagent.router.router.LiteLLMAgent", autospec=True)
    @patch("hackagent.router.router.ADKAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_agent_router_init_updates_existing_agent_if_metadata_differs(
        self,
        MockAgentMap,
        MockADKAdapter,
        MockLiteLLMAdapter,
    ):
        MockAgentMap[AgentTypeEnum.GOOGLE_ADK] = MockADKAdapter
        MockAgentMap[AgentTypeEnum.LITELLM] = MockLiteLLMAdapter
        MockADKAdapter.__name__ = "ADKAgent"
        MockLiteLLMAdapter.__name__ = "LiteLLMAgent"

        mock_org_id = uuid.uuid4()
        mock_backend = _make_backend(org_id=mock_org_id, user_id="456")
        existing_agent_id = uuid.uuid4()
        agent_name = "ExistingADKAgent"
        agent_endpoint = "http://new-endpoint.com/"
        new_metadata = {"new_key": "new_value", "common_key": "updated_from_router"}

        mock_backend.create_or_update_agent.return_value = _make_agent_rec(
            agent_id=existing_agent_id,
            name=agent_name,
            agent_type_str="GOOGLE_ADK",
            endpoint=agent_endpoint,
            metadata=new_metadata,
            org_id=mock_org_id,
        )

        router = AgentRouter(
            backend=mock_backend,
            name=agent_name,
            agent_type=AgentTypeEnum.GOOGLE_ADK,
            endpoint=agent_endpoint,
            metadata=new_metadata,
            adapter_operational_config={"user_id": "test_user_existing"},
            overwrite_metadata=True,
        )

        mock_backend.create_or_update_agent.assert_called_once_with(
            name=agent_name,
            agent_type=AgentTypeEnum.GOOGLE_ADK.value,
            endpoint=agent_endpoint,
            metadata=new_metadata,
            overwrite_metadata=True,
        )
        MockADKAdapter.assert_called_once()
        self.assertEqual(router.backend_agent.id, existing_agent_id)
        self.assertEqual(router.backend_agent.metadata, new_metadata)
        self.assertIn(str(existing_agent_id), router._agent_registry)

    @patch("hackagent.router.router.ADKAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_agent_router_init_existing_agent_metadata_matches_overwrite_true(
        self,
        MockAgentMap,
        MockADKAdapter,
    ):
        MockAgentMap[AgentTypeEnum.GOOGLE_ADK] = MockADKAdapter
        MockADKAdapter.__name__ = "ADKAgent"

        mock_org_id = uuid.uuid4()
        mock_backend = _make_backend(org_id=mock_org_id, user_id="789")
        existing_agent_id = uuid.uuid4()
        mock_backend.create_or_update_agent.return_value = _make_agent_rec(
            agent_id=existing_agent_id,
            name="ADKAgentMetaMatch",
            agent_type_str="GOOGLE_ADK",
            endpoint="http://current-endpoint.com/",
            metadata={"feature_flag": True, "version": "1.0.0"},
            org_id=mock_org_id,
        )

        router = AgentRouter(
            backend=mock_backend,
            name="ADKAgentMetaMatch",
            agent_type=AgentTypeEnum.GOOGLE_ADK,
            endpoint="http://current-endpoint.com/",
            metadata={"feature_flag": True, "version": "1.0.0"},
            adapter_operational_config={"user_id": "test_user_meta_match"},
            overwrite_metadata=True,
        )

        mock_backend.create_or_update_agent.assert_called_once()
        self.assertEqual(router.backend_agent.id, existing_agent_id)

    @patch("hackagent.router.router.ADKAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_agent_router_init_existing_agent_metadata_matches_overwrite_false(
        self,
        MockAgentMap,
        MockADKAdapter,
    ):
        MockAgentMap[AgentTypeEnum.GOOGLE_ADK] = MockADKAdapter
        MockADKAdapter.__name__ = "ADKAgent"

        mock_org_id = uuid.uuid4()
        mock_backend = _make_backend(org_id=mock_org_id, user_id="101112")
        existing_agent_id = uuid.uuid4()
        mock_backend.create_or_update_agent.return_value = _make_agent_rec(
            agent_id=existing_agent_id,
            name="ADKAgentMetaMatchOverwriteFalse",
            agent_type_str="GOOGLE_ADK",
            endpoint="http://current-endpoint-ow-false.com/",
            metadata={"feature_flag": True, "version": "1.0.1"},
            org_id=mock_org_id,
        )

        router = AgentRouter(
            backend=mock_backend,
            name="ADKAgentMetaMatchOverwriteFalse",
            agent_type=AgentTypeEnum.GOOGLE_ADK,
            endpoint="http://current-endpoint-ow-false.com/",
            metadata={"feature_flag": True, "version": "1.0.1"},
            adapter_operational_config={"user_id": "test_user_meta_match_ow_false"},
            overwrite_metadata=False,
        )

        mock_backend.create_or_update_agent.assert_called_once_with(
            name="ADKAgentMetaMatchOverwriteFalse",
            agent_type=AgentTypeEnum.GOOGLE_ADK.value,
            endpoint="http://current-endpoint-ow-false.com/",
            metadata={"feature_flag": True, "version": "1.0.1"},
            overwrite_metadata=False,
        )
        self.assertEqual(router.backend_agent.id, existing_agent_id)

    @patch("hackagent.router.router.ADKAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_agent_router_init_existing_agent_metadata_differs_overwrite_false(
        self,
        MockAgentMap,
        MockADKAdapter,
    ):
        MockAgentMap[AgentTypeEnum.GOOGLE_ADK] = MockADKAdapter
        MockADKAdapter.__name__ = "ADKAgent"

        mock_org_id = uuid.uuid4()
        mock_backend = _make_backend(org_id=mock_org_id, user_id="654")
        existing_agent_id = uuid.uuid4()
        existing_endpoint = "http://old-backend-endpoint.com"
        existing_metadata = {"old_key": "old_value", "common_key": "backend_version"}

        mock_backend.create_or_update_agent.return_value = _make_agent_rec(
            agent_id=existing_agent_id,
            name="ExistingADKAgentDiffMetaOverwriteFalse",
            agent_type_str="GOOGLE_ADK",
            endpoint=existing_endpoint,
            metadata=existing_metadata,
            org_id=mock_org_id,
        )

        router = AgentRouter(
            backend=mock_backend,
            name="ExistingADKAgentDiffMetaOverwriteFalse",
            agent_type=AgentTypeEnum.GOOGLE_ADK,
            endpoint="http://new-endpoint-for-router.com/",
            metadata={"new_key": "new_value", "common_key": "router_version"},
            adapter_operational_config={"user_id": "test_user_diff_meta_ow_false"},
            overwrite_metadata=False,
        )

        adapter_kwargs = MockADKAdapter.call_args[1]
        self.assertEqual(
            adapter_kwargs["config"]["name"], "ExistingADKAgentDiffMetaOverwriteFalse"
        )
        self.assertEqual(adapter_kwargs["config"]["endpoint"], existing_endpoint)
        self.assertEqual(router.backend_agent.id, existing_agent_id)
        self.assertEqual(router.backend_agent.metadata, existing_metadata)
        self.assertEqual(router.backend_agent.endpoint, existing_endpoint)

    @patch("hackagent.router.router.LiteLLMAgent", autospec=True)
    @patch("hackagent.router.router.ADKAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_agent_router_init_creates_new_litellm_agent(
        self,
        MockAgentMap,
        MockADKAdapter,
        MockLiteLLMAdapter,
    ):
        MockAgentMap[AgentTypeEnum.LITELLM] = MockLiteLLMAdapter
        MockAgentMap[AgentTypeEnum.GOOGLE_ADK] = MockADKAdapter
        MockADKAdapter.__name__ = "ADKAgent"
        MockLiteLLMAdapter.__name__ = "LiteLLMAgent"

        mock_org_id = uuid.uuid4()
        mock_backend = _make_backend(org_id=mock_org_id, user_id="789")
        created_id = uuid.uuid4()
        agent_name = "TestLiteLLMAgent"
        agent_endpoint = "http://litellm-router-endpoint.com/"
        agent_metadata = {"name": "gpt-3.5-turbo", "some_other_meta": "val"}
        adapter_op_config = {"api_key": "env_var_for_llm_key", "temperature": 0.8}

        mock_backend.create_or_update_agent.return_value = _make_agent_rec(
            agent_id=created_id,
            name=agent_name,
            agent_type_str="LITELLM",
            endpoint=agent_endpoint,
            metadata=agent_metadata,
            org_id=mock_org_id,
        )

        router = AgentRouter(
            backend=mock_backend,
            name=agent_name,
            agent_type=AgentTypeEnum.LITELLM,
            endpoint=agent_endpoint,
            metadata=agent_metadata,
            adapter_operational_config=adapter_op_config,
            overwrite_metadata=True,
        )

        MockADKAdapter.assert_not_called()
        MockLiteLLMAdapter.assert_called_once()
        mock_litellm_instance = MockLiteLLMAdapter.return_value
        adapter_kwargs = MockLiteLLMAdapter.call_args[1]
        self.assertEqual(adapter_kwargs["id"], str(created_id))
        actual_config = adapter_kwargs["config"]
        self.assertEqual(actual_config["name"], "gpt-3.5-turbo")
        self.assertEqual(actual_config["endpoint"], agent_endpoint)
        self.assertEqual(actual_config["api_key"], "env_var_for_llm_key")
        self.assertEqual(actual_config["temperature"], 0.8)
        self.assertIn(str(created_id), router._agent_registry)
        self.assertEqual(router._agent_registry[str(created_id)], mock_litellm_instance)


class TestAnyUrlEndpointConversion(unittest.TestCase):
    @patch("hackagent.router.router.ADKAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_adk_adapter_receives_str_endpoint_when_backend_returns_anyurl(
        self,
        MockAgentMap,
        MockADKAdapter,
    ):
        from pydantic import AnyUrl

        MockAgentMap[AgentTypeEnum.GOOGLE_ADK] = MockADKAdapter
        MockADKAdapter.__name__ = "ADKAgent"
        mock_backend = _make_backend()
        mock_backend.create_or_update_agent.return_value = _make_agent_rec(
            endpoint=AnyUrl("http://adk-endpoint.com/"),
            metadata={},
        )
        _ = AgentRouter(
            backend=mock_backend,
            name="TestADKAgent",
            agent_type=AgentTypeEnum.GOOGLE_ADK,
            endpoint="http://adk-endpoint.com/",
            metadata={},
            adapter_operational_config={"user_id": "uid-123"},
        )
        endpoint_value = MockADKAdapter.call_args[1]["config"]["endpoint"]
        self.assertIsInstance(endpoint_value, str)
        self.assertEqual(endpoint_value, "http://adk-endpoint.com/")

    @patch("hackagent.router.router.LiteLLMAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_litellm_adapter_receives_str_endpoint_when_backend_returns_anyurl(
        self,
        MockAgentMap,
        MockLiteLLMAdapter,
    ):
        from pydantic import AnyUrl

        MockAgentMap[AgentTypeEnum.LITELLM] = MockLiteLLMAdapter
        MockLiteLLMAdapter.__name__ = "LiteLLMAgent"
        mock_backend = _make_backend()
        mock_backend.create_or_update_agent.return_value = _make_agent_rec(
            agent_type_str="LITELLM",
            endpoint=AnyUrl("http://litellm-endpoint.com/"),
            metadata={"name": "gpt-4"},
        )
        _ = AgentRouter(
            backend=mock_backend,
            name="TestLiteLLMAgent",
            agent_type=AgentTypeEnum.LITELLM,
            endpoint="http://litellm-endpoint.com/",
            metadata={"name": "gpt-4"},
        )
        endpoint_value = MockLiteLLMAdapter.call_args[1]["config"]["endpoint"]
        self.assertIsInstance(endpoint_value, str)
        self.assertEqual(endpoint_value, "http://litellm-endpoint.com/")

    @patch("hackagent.router.router.OpenAIAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_openai_adapter_receives_str_endpoint_when_backend_returns_anyurl(
        self,
        MockAgentMap,
        MockOpenAIAdapter,
    ):
        from pydantic import AnyUrl

        MockAgentMap[AgentTypeEnum.OPENAI_SDK] = MockOpenAIAdapter
        MockOpenAIAdapter.__name__ = "OpenAIAgent"
        mock_backend = _make_backend()
        mock_backend.create_or_update_agent.return_value = _make_agent_rec(
            agent_type_str="OPENAI_SDK",
            endpoint=AnyUrl("http://openai-endpoint.com/v1/"),
            metadata={"name": "gpt-4o"},
        )
        _ = AgentRouter(
            backend=mock_backend,
            name="TestOpenAIAgent",
            agent_type=AgentTypeEnum.OPENAI_SDK,
            endpoint="http://openai-endpoint.com/v1/",
            metadata={"name": "gpt-4o"},
        )
        endpoint_value = MockOpenAIAdapter.call_args[1]["config"]["endpoint"]
        self.assertIsInstance(endpoint_value, str)
        self.assertEqual(endpoint_value, "http://openai-endpoint.com/v1/")

    @patch("hackagent.router.router.OllamaAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_ollama_adapter_receives_str_endpoint_when_backend_returns_anyurl(
        self,
        MockAgentMap,
        MockOllamaAdapter,
    ):
        from pydantic import AnyUrl

        MockAgentMap[AgentTypeEnum.OLLAMA] = MockOllamaAdapter
        MockOllamaAdapter.__name__ = "OllamaAgent"
        mock_backend = _make_backend()
        mock_backend.create_or_update_agent.return_value = _make_agent_rec(
            agent_type_str="OLLAMA",
            endpoint=AnyUrl("http://ollama-endpoint.com/"),
            metadata={"name": "llama3"},
        )
        _ = AgentRouter(
            backend=mock_backend,
            name="TestOllamaAgent",
            agent_type=AgentTypeEnum.OLLAMA,
            endpoint="http://ollama-endpoint.com/",
            metadata={"name": "llama3"},
        )
        endpoint_value = MockOllamaAdapter.call_args[1]["config"]["endpoint"]
        self.assertIsInstance(endpoint_value, str)
        self.assertEqual(endpoint_value, "http://ollama-endpoint.com/")


class TestMetadataNoneStripping(unittest.TestCase):
    @patch("hackagent.router.router.OllamaAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_none_values_stripped_from_metadata_on_create(
        self,
        MockAgentMap,
        MockOllamaAdapter,
    ):
        MockAgentMap[AgentTypeEnum.OLLAMA] = MockOllamaAdapter
        MockOllamaAdapter.__name__ = "OllamaAgent"
        mock_backend = _make_backend()
        mock_backend.create_or_update_agent.return_value = _make_agent_rec(
            agent_type_str="OLLAMA",
            endpoint="http://localhost:11434",
            metadata={
                "name": "llama2-uncensored",
                "endpoint": "http://localhost:11434",
            },
        )
        metadata_with_nones = {
            "name": "llama2-uncensored",
            "endpoint": "http://localhost:11434",
            "api_key": None,
            "max_new_tokens": None,
            "temperature": None,
            "top_p": None,
        }
        _ = AgentRouter(
            backend=mock_backend,
            name="llama2-uncensored",
            agent_type=AgentTypeEnum.OLLAMA,
            endpoint="http://localhost:11434",
            metadata=metadata_with_nones,
            adapter_operational_config={"name": "llama2-uncensored"},
        )
        mock_backend.create_or_update_agent.assert_called_once()
        sent_metadata = mock_backend.create_or_update_agent.call_args[1]["metadata"]
        null_keys = [k for k, v in sent_metadata.items() if v is None]
        self.assertEqual(null_keys, [], f"No null values allowed; found: {null_keys}")
        self.assertIn("name", sent_metadata)
        self.assertNotIn("api_key", sent_metadata)
        self.assertNotIn("max_new_tokens", sent_metadata)

    @patch("hackagent.router.router.OllamaAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_none_values_stripped_from_metadata_on_update(
        self,
        MockAgentMap,
        MockOllamaAdapter,
    ):
        MockAgentMap[AgentTypeEnum.OLLAMA] = MockOllamaAdapter
        MockOllamaAdapter.__name__ = "OllamaAgent"
        mock_backend = _make_backend()
        mock_backend.create_or_update_agent.return_value = _make_agent_rec(
            agent_type_str="OLLAMA",
            endpoint="http://localhost:11434",
            metadata={"name": "llama2-uncensored"},
        )
        metadata_with_nones = {
            "name": "llama2-uncensored",
            "endpoint": "http://localhost:11434",
            "api_key": None,
            "temperature": None,
        }
        _ = AgentRouter(
            backend=mock_backend,
            name="llama2-uncensored",
            agent_type=AgentTypeEnum.OLLAMA,
            endpoint="http://localhost:11434",
            metadata=metadata_with_nones,
            adapter_operational_config={"name": "llama2-uncensored"},
            overwrite_metadata=True,
        )
        mock_backend.create_or_update_agent.assert_called_once()
        sent_metadata = mock_backend.create_or_update_agent.call_args[1]["metadata"]
        null_keys = [k for k, v in sent_metadata.items() if v is None]
        self.assertEqual(null_keys, [], f"No null values allowed; found: {null_keys}")
        self.assertNotIn("api_key", sent_metadata)
        self.assertNotIn("temperature", sent_metadata)


class TestAgentPagination(unittest.TestCase):
    @patch("hackagent.router.router.LiteLLMAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_agent_found_on_page_two_is_not_recreated(
        self,
        MockAgentMap,
        MockLiteLLMAdapter,
    ):
        MockAgentMap[AgentTypeEnum.LITELLM] = MockLiteLLMAdapter
        MockLiteLLMAdapter.__name__ = "LiteLLMAgent"
        mock_backend = _make_backend()
        target_agent_id = uuid.uuid4()
        agent_name = "llama2-uncensored"
        mock_backend.create_or_update_agent.return_value = _make_agent_rec(
            agent_id=target_agent_id,
            name=agent_name,
            agent_type_str="LITELLM",
            endpoint="http://localhost:11434",
            metadata={"name": agent_name},
        )
        router = AgentRouter(
            backend=mock_backend,
            name=agent_name,
            agent_type=AgentTypeEnum.LITELLM,
            endpoint="http://localhost:11434",
            metadata={"name": agent_name},
            adapter_operational_config={"name": agent_name},
            overwrite_metadata=False,
        )
        mock_backend.create_or_update_agent.assert_called_once()
        self.assertEqual(router.backend_agent.name, agent_name)
        self.assertEqual(router.backend_agent.id, target_agent_id)


if __name__ == "__main__":
    unittest.main()
