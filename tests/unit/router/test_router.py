# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest
import uuid
from unittest.mock import MagicMock, patch
from hackagent.client import AuthenticatedClient
from hackagent.api.models import Agent as BackendAgentModel

# Assuming AgentTypeEnum and other necessary enums/models are accessible
# Models live in hackagent.api.models
from hackagent.router.types import AgentTypeEnum
from hackagent.router.router import AgentRouter


class TestAgentRouterInitialization(unittest.TestCase):
    @patch("hackagent.router.router.agent_list")
    @patch("hackagent.router.router.agent_create")
    @patch("hackagent.router.router.agent_partial_update")
    @patch("hackagent.router.router.LiteLLMAgent", autospec=True)
    @patch("hackagent.router.router.ADKAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_agent_router_init_creates_new_agent_if_not_exists(
        self,
        MockAgentMap,
        MockADKAdapter,
        MockLiteLLMAdapter,
        mock_agent_partial_update,
        mock_agent_create,
        mock_agent_list,
    ):
        # --- MOCK SETUP ---
        MockAgentMap[AgentTypeEnum.GOOGLE_ADK] = MockADKAdapter
        MockAgentMap[AgentTypeEnum.LITELLM] = MockLiteLLMAdapter

        MockADKAdapter.__name__ = "ADKAgent"
        MockLiteLLMAdapter.__name__ = "LiteLLMAgent"

        mock_client = MagicMock(spec=AuthenticatedClient)
        mock_client.token = "test_token_prefix_12345"

        mock_org_id = uuid.uuid4()
        mock_user_id = 123

        # Mock an initial agent for org/user ID fetching
        mock_initial_agent = MagicMock(spec=BackendAgentModel)
        mock_initial_agent.organization = mock_org_id
        mock_initial_agent.owner = mock_user_id
        mock_initial_agent.name = "existing_agent_for_org_user"

        # First two calls to agent_list are for fetching org and user IDs
        # Third call is for finding existing agent (which returns empty)
        mock_agent_list_responses = [
            # First call: _fetch_organization_id
            MagicMock(
                status_code=200,
                parsed=MagicMock(results=[mock_initial_agent], next=None),
            ),
            # Second call: _fetch_user_id_str
            MagicMock(
                status_code=200,
                parsed=MagicMock(results=[mock_initial_agent], next=None),
            ),
            # Third call: _find_existing_agent
            MagicMock(status_code=200, parsed=MagicMock(results=[], next=None)),
        ]
        mock_agent_list.sync_detailed.side_effect = mock_agent_list_responses

        mock_created_agent_id = uuid.uuid4()
        mock_backend_agent_from_create = MagicMock(spec=BackendAgentModel)
        mock_backend_agent_from_create.id = mock_created_agent_id
        mock_backend_agent_from_create.name = "TestAgent"
        mock_backend_agent_from_create.agent_type = AgentTypeEnum.GOOGLE_ADK
        mock_backend_agent_from_create.endpoint = "http://fake-agent-endpoint.com/"
        mock_backend_agent_from_create.metadata = {"initial_meta": "value"}
        mock_backend_agent_from_create.organization = mock_org_id

        mock_agent_create_response = MagicMock()
        mock_agent_create_response.status_code = 201
        mock_agent_create_response.parsed = mock_backend_agent_from_create
        mock_agent_create.sync_detailed.return_value = mock_agent_create_response

        # --- TEST PARAMETERS ---
        agent_name = "TestAgent"
        agent_type = AgentTypeEnum.GOOGLE_ADK
        agent_endpoint = "http://fake-agent-endpoint.com/"
        agent_metadata = {"initial_meta": "value"}
        adapter_op_config = {"user_id": "test_user_from_op_config"}

        # --- EXECUTE ---
        router = AgentRouter(
            client=mock_client,
            name=agent_name,
            agent_type=agent_type,
            endpoint=agent_endpoint,
            metadata=agent_metadata,
            adapter_operational_config=adapter_op_config,
            overwrite_metadata=True,
        )

        # --- ASSERTIONS ---
        # agent_list called 3 times: org ID, user ID, find existing agent
        self.assertEqual(mock_agent_list.sync_detailed.call_count, 3)
        mock_agent_create.sync_detailed.assert_called_once()
        create_call_args_kwargs = mock_agent_create.sync_detailed.call_args[1]
        self.assertEqual(create_call_args_kwargs["client"], mock_client)
        agent_request_body = create_call_args_kwargs["body"]
        self.assertEqual(agent_request_body.name, agent_name)
        self.assertEqual(agent_request_body.agent_type, agent_type)
        self.assertEqual(str(agent_request_body.endpoint), agent_endpoint)
        self.assertEqual(agent_request_body.metadata, agent_metadata)
        # Note: organization is set by backend based on authenticated user, not in requestuser, not in request

        mock_agent_partial_update.sync_detailed.assert_not_called()

        MockADKAdapter.assert_called_once()

        mock_adk_adapter_instance_created = MockADKAdapter.return_value
        adapter_constructor_call_args = MockADKAdapter.call_args
        self.assertIsNotNone(adapter_constructor_call_args)
        adapter_constructor_kwargs = adapter_constructor_call_args[1]
        self.assertEqual(adapter_constructor_kwargs["id"], str(mock_created_agent_id))
        expected_adapter_config = {
            "user_id": "test_user_from_op_config",
            "name": agent_name,
            "endpoint": agent_endpoint,
        }
        self.assertEqual(adapter_constructor_kwargs["config"], expected_adapter_config)

        MockLiteLLMAdapter.assert_not_called()

        self.assertEqual(router.client, mock_client)
        self.assertIsNotNone(router.backend_agent)
        self.assertEqual(router.backend_agent.id, mock_created_agent_id)
        self.assertEqual(router.backend_agent.name, agent_name)
        expected_registry_key = str(mock_created_agent_id)
        self.assertIn(expected_registry_key, router._agent_registry)
        self.assertEqual(
            router._agent_registry[expected_registry_key],
            mock_adk_adapter_instance_created,
        )

    @patch("hackagent.router.router.agent_list")
    @patch("hackagent.router.router.agent_create")
    @patch("hackagent.router.router.agent_partial_update")
    @patch("hackagent.router.router.LiteLLMAgent", autospec=True)
    @patch("hackagent.router.router.ADKAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_agent_router_init_updates_existing_agent_if_metadata_differs(
        self,
        MockAgentMap,
        MockADKAdapter,
        MockLiteLLMAdapter,
        mock_agent_partial_update,
        mock_agent_create,
        mock_agent_list,
    ):
        # --- MOCK SETUP ---
        MockAgentMap[AgentTypeEnum.GOOGLE_ADK] = MockADKAdapter
        MockAgentMap[AgentTypeEnum.LITELLM] = MockLiteLLMAdapter
        MockADKAdapter.__name__ = "ADKAgent"
        MockLiteLLMAdapter.__name__ = "LiteLLMAgent"

        mock_client = MagicMock(spec=AuthenticatedClient)
        mock_client.token = "test_token_prefix_existing_agent"

        mock_org_id = uuid.uuid4()
        mock_user_id = 456

        agent_name = "ExistingADKAgent"
        agent_type = AgentTypeEnum.GOOGLE_ADK
        agent_endpoint_from_router_init = "http://new-endpoint.com/"
        new_metadata_from_router_init = {
            "new_key": "new_value",
            "common_key": "updated_from_router",
        }
        adapter_op_config = {"user_id": "test_user_existing"}

        existing_agent_id = uuid.uuid4()
        existing_agent_mock = MagicMock(spec=BackendAgentModel)
        existing_agent_mock.id = existing_agent_id
        existing_agent_mock.name = agent_name
        existing_agent_mock.agent_type = agent_type
        existing_agent_mock.organization = mock_org_id
        existing_agent_mock.owner = mock_user_id  # Must be int for _fetch_user_id_str
        existing_agent_mock.endpoint = "http://old-endpoint.com"
        existing_agent_mock.metadata = {
            "old_key": "old_value",
            "common_key": "old_common_value",
        }

        mock_agent_list_response = MagicMock()
        mock_agent_list_response.status_code = 200
        mock_agent_list_response.parsed = MagicMock()
        mock_agent_list_response.parsed.results = [existing_agent_mock]
        mock_agent_list_response.parsed.next = None
        mock_agent_list.sync_detailed.return_value = mock_agent_list_response

        updated_backend_agent_mock = MagicMock(spec=BackendAgentModel)
        updated_backend_agent_mock.id = existing_agent_id
        updated_backend_agent_mock.name = agent_name
        updated_backend_agent_mock.agent_type = agent_type
        updated_backend_agent_mock.organization = mock_org_id
        updated_backend_agent_mock.endpoint = agent_endpoint_from_router_init
        updated_backend_agent_mock.metadata = new_metadata_from_router_init

        mock_agent_update_response = MagicMock()
        mock_agent_update_response.status_code = 200
        mock_agent_update_response.parsed = updated_backend_agent_mock
        mock_agent_partial_update.sync_detailed.return_value = (
            mock_agent_update_response
        )

        # --- EXECUTE ---
        router = AgentRouter(
            client=mock_client,
            name=agent_name,
            agent_type=agent_type,
            endpoint=agent_endpoint_from_router_init,
            metadata=new_metadata_from_router_init,
            adapter_operational_config=adapter_op_config,
            overwrite_metadata=True,
        )

        # --- ASSERTIONS ---
        # agent_list called 3 times: org ID, user ID, find existing agent
        self.assertEqual(mock_agent_list.sync_detailed.call_count, 3)
        mock_agent_create.sync_detailed.assert_not_called()
        mock_agent_partial_update.sync_detailed.assert_called_once()

        update_call_args_kwargs = mock_agent_partial_update.sync_detailed.call_args[1]
        self.assertEqual(update_call_args_kwargs["id"], existing_agent_id)

        expected_patched_metadata = {
            "old_key": "old_value",
            "common_key": "updated_from_router",
            "new_key": "new_value",
        }
        self.assertEqual(
            update_call_args_kwargs["body"].metadata, expected_patched_metadata
        )

        MockADKAdapter.assert_called_once()
        mock_adk_adapter_instance_created = MockADKAdapter.return_value
        adapter_constructor_call_args = MockADKAdapter.call_args
        self.assertIsNotNone(adapter_constructor_call_args)
        adapter_constructor_kwargs = adapter_constructor_call_args[1]
        self.assertEqual(adapter_constructor_kwargs["id"], str(existing_agent_id))

        expected_adapter_config = {
            "user_id": "test_user_existing",
            "name": agent_name,
            "endpoint": agent_endpoint_from_router_init,
        }
        self.assertEqual(adapter_constructor_kwargs["config"], expected_adapter_config)

        MockLiteLLMAdapter.assert_not_called()

        self.assertEqual(router.client, mock_client)
        self.assertIsNotNone(router.backend_agent)
        self.assertEqual(router.backend_agent, updated_backend_agent_mock)
        self.assertEqual(router.backend_agent.id, existing_agent_id)
        self.assertEqual(router.backend_agent.metadata, new_metadata_from_router_init)
        self.assertEqual(
            str(router.backend_agent.endpoint), agent_endpoint_from_router_init
        )

        expected_registry_key = str(existing_agent_id)
        self.assertIn(expected_registry_key, router._agent_registry)
        self.assertEqual(
            router._agent_registry[expected_registry_key],
            mock_adk_adapter_instance_created,
        )

    @patch("hackagent.router.router.agent_list")
    @patch("hackagent.router.router.agent_create")
    @patch("hackagent.router.router.agent_partial_update")
    @patch("hackagent.router.router.LiteLLMAgent", autospec=True)
    @patch("hackagent.router.router.ADKAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_agent_router_init_existing_agent_metadata_matches_overwrite_true(
        self,
        MockAgentMap,
        MockADKAdapter,
        MockLiteLLMAdapter,
        mock_agent_partial_update,
        mock_agent_create,
        mock_agent_list,
    ):
        # --- MOCK SETUP ---
        MockAgentMap[AgentTypeEnum.GOOGLE_ADK] = MockADKAdapter
        MockADKAdapter.__name__ = "ADKAgent"
        # MockLiteLLMAdapter not used in this specific ADK test but keep for consistency
        MockLiteLLMAdapter.__name__ = "LiteLLMAgent"

        mock_client = MagicMock(spec=AuthenticatedClient)
        mock_client.token = "test_token_metadata_m_atch_suffix"

        mock_org_id = uuid.uuid4()
        mock_user_id = 789

        agent_name = "ADKAgentMetaMatch"
        agent_type = AgentTypeEnum.GOOGLE_ADK
        # Metadata and endpoint that will be passed to AgentRouter init
        # and will be mocked as already existing in the backend.
        current_metadata = {"feature_flag": True, "version": "1.0.0"}
        current_endpoint = "http://current-endpoint.com/"
        adapter_op_config = {"user_id": "test_user_meta_match"}

        # Mock agent_list to return an existing agent with THE SAME metadata and endpoint
        existing_agent_id = uuid.uuid4()
        existing_agent_mock = MagicMock(spec=BackendAgentModel)
        existing_agent_mock.id = existing_agent_id
        existing_agent_mock.name = agent_name
        existing_agent_mock.agent_type = agent_type
        existing_agent_mock.organization = mock_org_id
        existing_agent_mock.owner = mock_user_id  # Must be int for _fetch_user_id_str
        existing_agent_mock.endpoint = (
            current_endpoint  # Matches what router init receives
        )
        existing_agent_mock.metadata = (
            current_metadata  # Matches what router init receives
        )

        mock_agent_list_response = MagicMock()
        mock_agent_list_response.status_code = 200
        mock_agent_list_response.parsed = MagicMock()
        mock_agent_list_response.parsed.results = [existing_agent_mock]
        mock_agent_list_response.parsed.next = None
        mock_agent_list.sync_detailed.return_value = mock_agent_list_response

        # --- EXECUTE ---
        router = AgentRouter(
            client=mock_client,
            name=agent_name,
            agent_type=agent_type,
            endpoint=current_endpoint,  # Same as existing
            metadata=current_metadata,  # Same as existing
            adapter_operational_config=adapter_op_config,
            overwrite_metadata=False,  # Key: Overwrite is False
        )

        # --- ASSERTIONS ---
        # agent_list called 3 times: org ID, user ID, find existing agent
        self.assertEqual(mock_agent_list.sync_detailed.call_count, 3)

        mock_agent_create.sync_detailed.assert_not_called()  # Should NOT createT update

        MockADKAdapter.assert_called_once()
        mock_adk_adapter_instance_created = MockADKAdapter.return_value

        adapter_constructor_call_args = MockADKAdapter.call_args
        adapter_constructor_kwargs = adapter_constructor_call_args[1]
        self.assertEqual(adapter_constructor_kwargs["id"], str(existing_agent_id))
        expected_adapter_config = {
            "user_id": "test_user_meta_match",
            "name": agent_name,
            "endpoint": current_endpoint,
        }
        self.assertEqual(adapter_constructor_kwargs["config"], expected_adapter_config)

        MockLiteLLMAdapter.assert_not_called()

        # Router's internal state should reflect the agent returned by agent_list (no update happened)
        self.assertEqual(router.client, mock_client)
        self.assertIsNotNone(router.backend_agent)
        # self.assertEqual(router.backend_agent, existing_agent_mock) # Direct object comparison
        self.assertEqual(router.backend_agent.id, existing_agent_id)
        self.assertEqual(router.backend_agent.metadata, current_metadata)
        self.assertEqual(str(router.backend_agent.endpoint), current_endpoint)

        expected_registry_key = str(existing_agent_id)
        self.assertIn(expected_registry_key, router._agent_registry)
        self.assertEqual(
            router._agent_registry[expected_registry_key],
            mock_adk_adapter_instance_created,
        )

    @patch("hackagent.router.router.agent_list")
    @patch("hackagent.router.router.agent_create")
    @patch("hackagent.router.router.agent_partial_update")
    @patch("hackagent.router.router.LiteLLMAgent", autospec=True)
    @patch("hackagent.router.router.ADKAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_agent_router_init_existing_agent_metadata_matches_overwrite_false(
        self,
        MockAgentMap,
        MockADKAdapter,
        MockLiteLLMAdapter,
        mock_agent_partial_update,
        mock_agent_create,
        mock_agent_list,
    ):
        # --- MOCK SETUP ---
        MockAgentMap[AgentTypeEnum.GOOGLE_ADK] = MockADKAdapter
        MockADKAdapter.__name__ = "ADKAgent"
        MockLiteLLMAdapter.__name__ = "LiteLLMAgent"

        mock_client = MagicMock(spec=AuthenticatedClient)
        mock_client.token = "test_token_meta_match_overwrite_false"

        mock_org_id = uuid.uuid4()
        mock_user_id = 101112

        agent_name = "ADKAgentMetaMatchOverwriteFalse"
        agent_type = AgentTypeEnum.GOOGLE_ADK
        current_metadata = {"feature_flag": True, "version": "1.0.1"}
        current_endpoint = "http://current-endpoint-ow-false.com/"
        adapter_op_config = {"user_id": "test_user_meta_match_ow_false"}

        existing_agent_id = uuid.uuid4()
        existing_agent_mock = MagicMock(spec=BackendAgentModel)
        existing_agent_mock.id = existing_agent_id
        existing_agent_mock.name = agent_name
        existing_agent_mock.agent_type = agent_type
        existing_agent_mock.organization = mock_org_id
        existing_agent_mock.owner = mock_user_id  # Must be int for _fetch_user_id_str
        existing_agent_mock.endpoint = current_endpoint
        existing_agent_mock.metadata = current_metadata

        mock_agent_list_response = MagicMock()
        mock_agent_list_response.status_code = 200
        mock_agent_list_response.parsed = MagicMock()
        mock_agent_list_response.parsed.results = [existing_agent_mock]
        mock_agent_list_response.parsed.next = None
        mock_agent_list.sync_detailed.return_value = mock_agent_list_response

        # --- EXECUTE ---
        router = AgentRouter(
            client=mock_client,
            name=agent_name,
            agent_type=agent_type,
            endpoint=current_endpoint,
            metadata=current_metadata,
            adapter_operational_config=adapter_op_config,
            overwrite_metadata=False,  # Key change for this test
        )

        # --- ASSERTIONS ---
        # agent_list called 3 times: org ID, user ID, find existing agent
        self.assertEqual(mock_agent_list.sync_detailed.call_count, 3)

        mock_agent_create.sync_detailed.assert_not_called()
        mock_agent_partial_update.sync_detailed.assert_not_called()  # Should NOT update

        MockADKAdapter.assert_called_once()
        mock_adk_adapter_instance_created = MockADKAdapter.return_value

        adapter_constructor_call_args = MockADKAdapter.call_args
        adapter_constructor_kwargs = adapter_constructor_call_args[1]
        self.assertEqual(adapter_constructor_kwargs["id"], str(existing_agent_id))
        expected_adapter_config = {
            "user_id": "test_user_meta_match_ow_false",
            "name": agent_name,
            "endpoint": current_endpoint,
        }
        self.assertEqual(adapter_constructor_kwargs["config"], expected_adapter_config)

        MockLiteLLMAdapter.assert_not_called()

        self.assertEqual(router.client, mock_client)
        self.assertIsNotNone(router.backend_agent)
        self.assertEqual(router.backend_agent.id, existing_agent_id)
        self.assertEqual(router.backend_agent.metadata, current_metadata)
        self.assertEqual(str(router.backend_agent.endpoint), current_endpoint)

        expected_registry_key = str(existing_agent_id)
        self.assertIn(expected_registry_key, router._agent_registry)
        self.assertEqual(
            router._agent_registry[expected_registry_key],
            mock_adk_adapter_instance_created,
        )

    @patch("hackagent.router.router.agent_list")
    @patch("hackagent.router.router.agent_create")
    @patch("hackagent.router.router.agent_partial_update")
    @patch("hackagent.router.router.LiteLLMAgent", autospec=True)
    @patch("hackagent.router.router.ADKAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_agent_router_init_existing_agent_metadata_differs_overwrite_false(
        self,
        MockAgentMap,
        MockADKAdapter,
        MockLiteLLMAdapter,
        mock_agent_partial_update,
        mock_agent_create,
        mock_agent_list,
    ):
        # --- MOCK SETUP ---
        MockAgentMap[AgentTypeEnum.GOOGLE_ADK] = MockADKAdapter
        MockADKAdapter.__name__ = "ADKAgent"
        MockLiteLLMAdapter.__name__ = "LiteLLMAgent"

        mock_client = MagicMock(spec=AuthenticatedClient)
        mock_client.token = "test_token_diff_meta_ow_false"
        mock_org_id = uuid.uuid4()
        mock_user_id = 654

        agent_name = "ExistingADKAgentDiffMetaOverwriteFalse"
        agent_type = AgentTypeEnum.GOOGLE_ADK

        # Metadata for AgentRouter init (DIFFERENT from existing)
        router_init_endpoint = "http://new-endpoint-for-router.com/"
        router_init_metadata = {"new_key": "new_value", "common_key": "router_version"}
        adapter_op_config = {"user_id": "test_user_diff_meta_ow_false"}

        # Mock existing agent in the backend (with OLD metadata)
        existing_agent_id = uuid.uuid4()
        existing_agent_mock = MagicMock(spec=BackendAgentModel)
        existing_agent_mock.id = existing_agent_id
        existing_agent_mock.name = agent_name
        existing_agent_mock.agent_type = agent_type
        existing_agent_mock.organization = mock_org_id
        existing_agent_mock.owner = mock_user_id  # Must be int for _fetch_user_id_str
        existing_agent_mock.endpoint = (
            "http://old-backend-endpoint.com"  # Different from router_init_endpoint
        )
        existing_agent_mock.metadata = {
            "old_key": "old_value",
            "common_key": "backend_version",
        }  # Different

        # Mock an initial agent for org/user ID fetching
        mock_initial_agent = MagicMock(spec=BackendAgentModel)
        mock_initial_agent.organization = mock_org_id
        mock_initial_agent.owner = mock_user_id
        mock_initial_agent.name = "initial_agent_for_ids"

        # agent_list called 3 times: org ID fetch, user ID fetch, find existing agent
        mock_agent_list_responses = [
            MagicMock(
                status_code=200,
                parsed=MagicMock(results=[mock_initial_agent], next=None),
            ),
            MagicMock(
                status_code=200,
                parsed=MagicMock(results=[mock_initial_agent], next=None),
            ),
            MagicMock(
                status_code=200,
                parsed=MagicMock(results=[existing_agent_mock], next=None),
            ),
        ]
        mock_agent_list.sync_detailed.side_effect = mock_agent_list_responses

        # --- EXECUTE ---
        router = AgentRouter(
            client=mock_client,
            name=agent_name,
            agent_type=agent_type,
            endpoint=router_init_endpoint,
            metadata=router_init_metadata,
            adapter_operational_config=adapter_op_config,
            overwrite_metadata=False,  # Key: Overwrite is False
        )

        # --- ASSERTIONS ---
        # agent_list called 3 times: org ID, user ID, find existing agent
        self.assertEqual(mock_agent_list.sync_detailed.call_count, 3)

        mock_agent_create.sync_detailed.assert_not_called()  # Should NOT create
        mock_agent_partial_update.sync_detailed.assert_not_called()  # Should NOT update

        MockADKAdapter.assert_called_once()
        mock_adk_adapter_instance_created = MockADKAdapter.return_value

        adapter_constructor_call_args = MockADKAdapter.call_args
        adapter_constructor_kwargs = adapter_constructor_call_args[1]
        self.assertEqual(adapter_constructor_kwargs["id"], str(existing_agent_id))

        # Adapter config should use the backend agent's actual endpoint and name
        # because no update occurred. Metadata is not directly part of ADK adapter config here.
        expected_adapter_config = {
            "user_id": "test_user_diff_meta_ow_false",
            "name": existing_agent_mock.name,  # From backend
            "endpoint": existing_agent_mock.endpoint,  # From backend
        }
        self.assertEqual(adapter_constructor_kwargs["config"], expected_adapter_config)

        MockLiteLLMAdapter.assert_not_called()

        # Router's backend_agent should be the one found, UNCHANGED
        self.assertEqual(router.client, mock_client)
        self.assertIsNotNone(router.backend_agent)
        self.assertEqual(
            router.backend_agent, existing_agent_mock
        )  # Check it's the original mock
        self.assertEqual(router.backend_agent.id, existing_agent_id)
        self.assertEqual(
            router.backend_agent.metadata, existing_agent_mock.metadata
        )  # Should be old metadata
        self.assertEqual(
            router.backend_agent.endpoint, existing_agent_mock.endpoint
        )  # Should be old endpoint

        expected_registry_key = str(existing_agent_id)
        self.assertIn(expected_registry_key, router._agent_registry)
        self.assertEqual(
            router._agent_registry[expected_registry_key],
            mock_adk_adapter_instance_created,
        )

    @patch("hackagent.router.router.agent_list")
    @patch("hackagent.router.router.agent_create")
    @patch("hackagent.router.router.agent_partial_update")
    @patch("hackagent.router.router.LiteLLMAgent", autospec=True)
    @patch("hackagent.router.router.ADKAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_agent_router_init_creates_new_litellm_agent(
        self,
        MockAgentMap,
        MockADKAdapter,
        MockLiteLLMAdapter,
        mock_agent_partial_update,
        mock_agent_create,
        mock_agent_list,
    ):
        # --- MOCK SETUP ---
        MockAgentMap[AgentTypeEnum.LITELLM] = MockLiteLLMAdapter
        # Need to map ADK as well, even if not called, as AGENT_TYPE_TO_ADAPTER_MAP is fully replaced
        MockAgentMap[AgentTypeEnum.GOOGLE_ADK] = MockADKAdapter
        MockADKAdapter.__name__ = "ADKAgent"
        MockLiteLLMAdapter.__name__ = "LiteLLMAgent"

        mock_client = MagicMock(spec=AuthenticatedClient)
        mock_client.token = "test_token_litellm_create"
        mock_org_id = uuid.uuid4()
        mock_user_id = 789

        # Mock agent_list to return no existing agents
        # Mock an initial agent for org/user ID fetching
        mock_initial_agent = MagicMock(spec=BackendAgentModel)
        mock_initial_agent.organization = mock_org_id
        mock_initial_agent.owner = mock_user_id
        mock_initial_agent.name = "existing_agent_for_org_user"

        # First two calls to agent_list are for fetching org and user IDs
        # Third call is for finding existing agent (which returns empty)
        mock_agent_list_responses = [
            # First call: _fetch_organization_id
            MagicMock(
                status_code=200,
                parsed=MagicMock(results=[mock_initial_agent], next=None),
            ),
            # Second call: _fetch_user_id_str
            MagicMock(
                status_code=200,
                parsed=MagicMock(results=[mock_initial_agent], next=None),
            ),
            # Third call: _find_existing_agent
            MagicMock(status_code=200, parsed=MagicMock(results=[], next=None)),
        ]
        mock_agent_list.sync_detailed.side_effect = mock_agent_list_responses

        # Mock agent_create response
        created_litellm_agent_id = uuid.uuid4()
        mock_backend_agent_from_create = MagicMock(spec=BackendAgentModel)
        mock_backend_agent_from_create.id = created_litellm_agent_id
        mock_backend_agent_from_create.name = "TestLiteLLMAgent"
        mock_backend_agent_from_create.agent_type = AgentTypeEnum.LITELLM
        mock_backend_agent_from_create.endpoint = (
            "http://litellm-router-endpoint.com/"  # Endpoint for router registration
        )
        # For LiteLLM, metadata often includes the actual model name and provider details
        mock_backend_agent_from_create.metadata = {
            "name": "gpt-3.5-turbo",
            "some_other_meta": "val",
        }
        mock_backend_agent_from_create.organization = mock_org_id

        mock_agent_create_response = MagicMock()
        mock_agent_create_response.status_code = 201
        mock_agent_create_response.parsed = mock_backend_agent_from_create
        mock_agent_create.sync_detailed.return_value = mock_agent_create_response

        # --- TEST PARAMETERS ---
        agent_name_param = "TestLiteLLMAgent"
        agent_type_param = AgentTypeEnum.LITELLM
        # This endpoint is what the AgentRouter uses to register the agent with the backend.
        # The actual LLM endpoint might be within the metadata or adapter_op_config.
        agent_endpoint_param = "http://litellm-router-endpoint.com/"
        agent_metadata_param = {
            "name": "gpt-3.5-turbo",
            "some_other_meta": "val",
        }  # Model name for LiteLLM is crucial
        # Adapter operational config might provide overrides or API keys for LiteLLM
        adapter_op_config_param = {"api_key": "env_var_for_llm_key", "temperature": 0.8}

        # --- EXECUTE ---
        router = AgentRouter(
            client=mock_client,
            name=agent_name_param,
            agent_type=agent_type_param,
            endpoint=agent_endpoint_param,
            metadata=agent_metadata_param,
            adapter_operational_config=adapter_op_config_param,
            overwrite_metadata=True,
        )

        # --- ASSERTIONS ---
        # agent_list called 3 times: org ID, user ID, find existing agent
        self.assertEqual(mock_agent_list.sync_detailed.call_count, 3)
        mock_agent_create.sync_detailed.assert_called_once()

        create_call_args_kwargs = mock_agent_create.sync_detailed.call_args[1]
        agent_request_body = create_call_args_kwargs["body"]
        self.assertEqual(agent_request_body.name, agent_name_param)
        self.assertEqual(agent_request_body.agent_type, agent_type_param)
        self.assertEqual(str(agent_request_body.endpoint), agent_endpoint_param)
        self.assertEqual(agent_request_body.metadata, agent_metadata_param)
        # AgentRequest doesn't have organization field - it's managed by backend

        mock_agent_partial_update.sync_detailed.assert_not_called()
        MockADKAdapter.assert_not_called()  # ADK Adapter should not be called

        MockLiteLLMAdapter.assert_called_once()
        mock_litellm_adapter_instance = MockLiteLLMAdapter.return_value
        adapter_constructor_call_args = MockLiteLLMAdapter.call_args
        adapter_constructor_kwargs = adapter_constructor_call_args[1]
        self.assertEqual(
            adapter_constructor_kwargs["id"], str(created_litellm_agent_id)
        )

        # Assert the actual config passed to the LiteLLMAdapter constructor
        actual_adapter_config = adapter_constructor_kwargs["config"]
        expected_final_adapter_config = {
            "name": "gpt-3.5-turbo",  # From metadata (mock_backend_agent_from_create.metadata["name"])
            "endpoint": "http://litellm-router-endpoint.com/",  # From backend_agent.endpoint
            "api_key": "env_var_for_llm_key",  # From adapter_op_config_param
            "temperature": 0.8,  # From adapter_op_config_param
            # "some_other_meta": "val" # Apparently not included from metadata in the final config
        }
        self.assertEqual(actual_adapter_config, expected_final_adapter_config)

        self.assertEqual(router.backend_agent, mock_backend_agent_from_create)
        expected_registry_key = str(created_litellm_agent_id)
        self.assertIn(expected_registry_key, router._agent_registry)
        self.assertEqual(
            router._agent_registry[expected_registry_key], mock_litellm_adapter_instance
        )


class TestAnyUrlEndpointConversion(unittest.TestCase):
    """Verify that AnyUrl objects from Pydantic models are converted to plain str
    before being passed to adapter constructors (prevents 'AnyUrl has no .strip' errors)."""

    def _make_agent_list_side_effect(self, mock_org_id, mock_user_id):
        """Helper that returns the three standard agent_list responses."""
        mock_initial = MagicMock(spec=BackendAgentModel)
        mock_initial.organization = mock_org_id
        mock_initial.owner = mock_user_id
        mock_initial.name = "seed_agent"
        return [
            MagicMock(
                status_code=200, parsed=MagicMock(results=[mock_initial], next=None)
            ),
            MagicMock(
                status_code=200, parsed=MagicMock(results=[mock_initial], next=None)
            ),
            MagicMock(status_code=200, parsed=MagicMock(results=[], next=None)),
        ]

    @patch("hackagent.router.router.agent_list")
    @patch("hackagent.router.router.agent_create")
    @patch("hackagent.router.router.agent_partial_update")
    @patch("hackagent.router.router.ADKAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_adk_adapter_receives_str_endpoint_when_backend_returns_anyurl(
        self,
        MockAgentMap,
        MockADKAdapter,
        mock_agent_partial_update,
        mock_agent_create,
        mock_agent_list,
    ):
        """ADKAgent must receive endpoint as str, not AnyUrl, so .strip('/') works."""
        from pydantic import AnyUrl

        MockAgentMap[AgentTypeEnum.GOOGLE_ADK] = MockADKAdapter
        MockADKAdapter.__name__ = "ADKAgent"

        mock_client = MagicMock(spec=AuthenticatedClient)
        mock_client.token = "test_token"
        mock_org_id = uuid.uuid4()

        mock_agent_list.sync_detailed.side_effect = self._make_agent_list_side_effect(
            mock_org_id, 1
        )

        created_agent_id = uuid.uuid4()
        mock_backend_agent = MagicMock(spec=BackendAgentModel)
        mock_backend_agent.id = created_agent_id
        mock_backend_agent.name = "TestADKAgent"
        mock_backend_agent.agent_type = AgentTypeEnum.GOOGLE_ADK
        # Simulate Pydantic v2 returning an AnyUrl object instead of a plain string
        mock_backend_agent.endpoint = AnyUrl("http://adk-endpoint.com/")
        mock_backend_agent.metadata = {}
        mock_backend_agent.organization = mock_org_id

        mock_create_response = MagicMock()
        mock_create_response.status_code = 201
        mock_create_response.parsed = mock_backend_agent
        mock_agent_create.sync_detailed.return_value = mock_create_response

        _ = AgentRouter(
            client=mock_client,
            name="TestADKAgent",
            agent_type=AgentTypeEnum.GOOGLE_ADK,
            endpoint="http://adk-endpoint.com/",
            metadata={},
            adapter_operational_config={"user_id": "uid-123"},
        )

        MockADKAdapter.assert_called_once()
        adapter_config = MockADKAdapter.call_args[1]["config"]
        endpoint_value = adapter_config["endpoint"]
        self.assertIsInstance(
            endpoint_value,
            str,
            "endpoint passed to ADKAgent must be a plain str, not AnyUrl",
        )
        self.assertEqual(endpoint_value, "http://adk-endpoint.com/")

    @patch("hackagent.router.router.agent_list")
    @patch("hackagent.router.router.agent_create")
    @patch("hackagent.router.router.agent_partial_update")
    @patch("hackagent.router.router.LiteLLMAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_litellm_adapter_receives_str_endpoint_when_backend_returns_anyurl(
        self,
        MockAgentMap,
        MockLiteLLMAdapter,
        mock_agent_partial_update,
        mock_agent_create,
        mock_agent_list,
    ):
        """LiteLLMAgent must receive endpoint as str, not AnyUrl."""
        from pydantic import AnyUrl

        MockAgentMap[AgentTypeEnum.LITELLM] = MockLiteLLMAdapter
        MockLiteLLMAdapter.__name__ = "LiteLLMAgent"

        mock_client = MagicMock(spec=AuthenticatedClient)
        mock_client.token = "test_token"
        mock_org_id = uuid.uuid4()

        mock_agent_list.sync_detailed.side_effect = self._make_agent_list_side_effect(
            mock_org_id, 1
        )

        created_agent_id = uuid.uuid4()
        mock_backend_agent = MagicMock(spec=BackendAgentModel)
        mock_backend_agent.id = created_agent_id
        mock_backend_agent.name = "TestLiteLLMAgent"
        mock_backend_agent.agent_type = AgentTypeEnum.LITELLM
        mock_backend_agent.endpoint = AnyUrl("http://litellm-endpoint.com/")
        mock_backend_agent.metadata = {"name": "gpt-4"}
        mock_backend_agent.organization = mock_org_id

        mock_create_response = MagicMock()
        mock_create_response.status_code = 201
        mock_create_response.parsed = mock_backend_agent
        mock_agent_create.sync_detailed.return_value = mock_create_response

        _ = AgentRouter(
            client=mock_client,
            name="TestLiteLLMAgent",
            agent_type=AgentTypeEnum.LITELLM,
            endpoint="http://litellm-endpoint.com/",
            metadata={"name": "gpt-4"},
        )

        MockLiteLLMAdapter.assert_called_once()
        adapter_config = MockLiteLLMAdapter.call_args[1]["config"]
        endpoint_value = adapter_config["endpoint"]
        self.assertIsInstance(
            endpoint_value,
            str,
            "endpoint passed to LiteLLMAgent must be a plain str, not AnyUrl",
        )
        self.assertEqual(endpoint_value, "http://litellm-endpoint.com/")

    @patch("hackagent.router.router.agent_list")
    @patch("hackagent.router.router.agent_create")
    @patch("hackagent.router.router.agent_partial_update")
    @patch("hackagent.router.router.OpenAIAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_openai_adapter_receives_str_endpoint_when_backend_returns_anyurl(
        self,
        MockAgentMap,
        MockOpenAIAdapter,
        mock_agent_partial_update,
        mock_agent_create,
        mock_agent_list,
    ):
        """OpenAIAgent must receive endpoint as str, not AnyUrl."""
        from pydantic import AnyUrl

        MockAgentMap[AgentTypeEnum.OPENAI_SDK] = MockOpenAIAdapter
        MockOpenAIAdapter.__name__ = "OpenAIAgent"

        mock_client = MagicMock(spec=AuthenticatedClient)
        mock_client.token = "test_token"
        mock_org_id = uuid.uuid4()

        mock_agent_list.sync_detailed.side_effect = self._make_agent_list_side_effect(
            mock_org_id, 1
        )

        created_agent_id = uuid.uuid4()
        mock_backend_agent = MagicMock(spec=BackendAgentModel)
        mock_backend_agent.id = created_agent_id
        mock_backend_agent.name = "TestOpenAIAgent"
        mock_backend_agent.agent_type = AgentTypeEnum.OPENAI_SDK
        mock_backend_agent.endpoint = AnyUrl("http://openai-endpoint.com/v1/")
        mock_backend_agent.metadata = {"name": "gpt-4o"}
        mock_backend_agent.organization = mock_org_id

        mock_create_response = MagicMock()
        mock_create_response.status_code = 201
        mock_create_response.parsed = mock_backend_agent
        mock_agent_create.sync_detailed.return_value = mock_create_response

        _ = AgentRouter(
            client=mock_client,
            name="TestOpenAIAgent",
            agent_type=AgentTypeEnum.OPENAI_SDK,
            endpoint="http://openai-endpoint.com/v1/",
            metadata={"name": "gpt-4o"},
        )

        MockOpenAIAdapter.assert_called_once()
        adapter_config = MockOpenAIAdapter.call_args[1]["config"]
        endpoint_value = adapter_config["endpoint"]
        self.assertIsInstance(
            endpoint_value,
            str,
            "endpoint passed to OpenAIAgent must be a plain str, not AnyUrl",
        )
        self.assertEqual(endpoint_value, "http://openai-endpoint.com/v1/")

    @patch("hackagent.router.router.agent_list")
    @patch("hackagent.router.router.agent_create")
    @patch("hackagent.router.router.agent_partial_update")
    @patch("hackagent.router.router.OllamaAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_ollama_adapter_receives_str_endpoint_when_backend_returns_anyurl(
        self,
        MockAgentMap,
        MockOllamaAdapter,
        mock_agent_partial_update,
        mock_agent_create,
        mock_agent_list,
    ):
        """OllamaAgent must receive endpoint as str, not AnyUrl."""
        from pydantic import AnyUrl

        MockAgentMap[AgentTypeEnum.OLLAMA] = MockOllamaAdapter
        MockOllamaAdapter.__name__ = "OllamaAgent"

        mock_client = MagicMock(spec=AuthenticatedClient)
        mock_client.token = "test_token"
        mock_org_id = uuid.uuid4()

        mock_agent_list.sync_detailed.side_effect = self._make_agent_list_side_effect(
            mock_org_id, 1
        )

        created_agent_id = uuid.uuid4()
        mock_backend_agent = MagicMock(spec=BackendAgentModel)
        mock_backend_agent.id = created_agent_id
        mock_backend_agent.name = "TestOllamaAgent"
        mock_backend_agent.agent_type = AgentTypeEnum.OLLAMA
        mock_backend_agent.endpoint = AnyUrl("http://ollama-endpoint.com/")
        mock_backend_agent.metadata = {"name": "llama3"}
        mock_backend_agent.organization = mock_org_id

        mock_create_response = MagicMock()
        mock_create_response.status_code = 201
        mock_create_response.parsed = mock_backend_agent
        mock_agent_create.sync_detailed.return_value = mock_create_response

        _ = AgentRouter(
            client=mock_client,
            name="TestOllamaAgent",
            agent_type=AgentTypeEnum.OLLAMA,
            endpoint="http://ollama-endpoint.com/",
            metadata={"name": "llama3"},
        )

        MockOllamaAdapter.assert_called_once()
        adapter_config = MockOllamaAdapter.call_args[1]["config"]
        endpoint_value = adapter_config["endpoint"]
        self.assertIsInstance(
            endpoint_value,
            str,
            "endpoint passed to OllamaAgent must be a plain str, not AnyUrl",
        )
        self.assertEqual(endpoint_value, "http://ollama-endpoint.com/")


class TestMetadataNoneStripping(unittest.TestCase):
    """Verify that None values in metadata are stripped before backend calls.

    Django's JSONField rejects null values that arrive from Pydantic's
    model_dump() when optional config keys were not provided by the caller.
    """

    def _make_agent_list_side_effect(self, mock_org_id, mock_user_id):
        mock_initial = MagicMock(spec=BackendAgentModel)
        mock_initial.organization = mock_org_id
        mock_initial.owner = mock_user_id
        mock_initial.name = "seed_agent"
        return [
            MagicMock(
                status_code=200, parsed=MagicMock(results=[mock_initial], next=None)
            ),
            MagicMock(
                status_code=200, parsed=MagicMock(results=[mock_initial], next=None)
            ),
            MagicMock(status_code=200, parsed=MagicMock(results=[], next=None)),
        ]

    @patch("hackagent.router.router.agent_list")
    @patch("hackagent.router.router.agent_create")
    @patch("hackagent.router.router.agent_partial_update")
    @patch("hackagent.router.router.OllamaAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_none_values_stripped_from_metadata_on_create(
        self,
        MockAgentMap,
        MockOllamaAdapter,
        mock_agent_partial_update,
        mock_agent_create,
        mock_agent_list,
    ):
        """AgentRequest sent to backend must not contain null values in metadata dict."""
        MockAgentMap[AgentTypeEnum.OLLAMA] = MockOllamaAdapter
        MockOllamaAdapter.__name__ = "OllamaAgent"

        mock_client = MagicMock(spec=AuthenticatedClient)
        mock_client.token = "test_token"
        mock_org_id = uuid.uuid4()

        mock_agent_list.sync_detailed.side_effect = self._make_agent_list_side_effect(
            mock_org_id, 1
        )

        created_agent_id = uuid.uuid4()
        mock_backend_agent = MagicMock(spec=BackendAgentModel)
        mock_backend_agent.id = created_agent_id
        mock_backend_agent.name = "llama2-uncensored"
        mock_backend_agent.agent_type = AgentTypeEnum.OLLAMA
        mock_backend_agent.endpoint = "http://localhost:11434"
        mock_backend_agent.metadata = {
            "name": "llama2-uncensored",
            "endpoint": "http://localhost:11434",
        }
        mock_backend_agent.organization = mock_org_id

        mock_create_response = MagicMock()
        mock_create_response.status_code = 201
        mock_create_response.parsed = mock_backend_agent
        mock_agent_create.sync_detailed.return_value = mock_create_response

        # Metadata as it comes from _initialize_generation_router — many None values
        metadata_with_nones = {
            "name": "llama2-uncensored",
            "endpoint": "http://localhost:11434",
            "api_key": None,
            "max_new_tokens": None,
            "temperature": None,
            "top_p": None,
        }

        _ = AgentRouter(
            client=mock_client,
            name="llama2-uncensored",
            agent_type=AgentTypeEnum.OLLAMA,
            endpoint="http://localhost:11434",
            metadata=metadata_with_nones,
            adapter_operational_config={"name": "llama2-uncensored"},
        )

        # Check the AgentRequest body passed to agent_create
        mock_agent_create.sync_detailed.assert_called_once()
        create_kwargs = mock_agent_create.sync_detailed.call_args[1]
        body = create_kwargs["body"]

        # Serialize the body the same way the API layer does
        from hackagent.api.models import AgentRequest

        self.assertIsInstance(body, AgentRequest)
        payload = body.model_dump(by_alias=True, mode="json", exclude_none=True)

        # metadata must not contain any null values
        sent_metadata = payload.get("metadata", {})
        null_keys = [k for k, v in sent_metadata.items() if v is None]
        self.assertEqual(
            null_keys,
            [],
            f"metadata in HTTP payload must have no null values; found nulls for: {null_keys}",
        )

        # Only keys with real values should be present
        self.assertIn("name", sent_metadata)
        self.assertIn("endpoint", sent_metadata)
        self.assertNotIn("api_key", sent_metadata)
        self.assertNotIn("max_new_tokens", sent_metadata)
        self.assertNotIn("temperature", sent_metadata)
        self.assertNotIn("top_p", sent_metadata)

    @patch("hackagent.router.router.agent_list")
    @patch("hackagent.router.router.agent_create")
    @patch("hackagent.router.router.agent_partial_update")
    @patch("hackagent.router.router.OllamaAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_none_values_stripped_from_metadata_on_update(
        self,
        MockAgentMap,
        MockOllamaAdapter,
        mock_agent_partial_update,
        mock_agent_create,
        mock_agent_list,
    ):
        """PatchedAgentRequest sent on update must not contain null values in metadata."""
        MockAgentMap[AgentTypeEnum.OLLAMA] = MockOllamaAdapter
        MockOllamaAdapter.__name__ = "OllamaAgent"

        mock_client = MagicMock(spec=AuthenticatedClient)
        mock_client.token = "test_token"
        mock_org_id = uuid.uuid4()

        existing_agent_id = uuid.uuid4()
        mock_existing_agent = MagicMock(spec=BackendAgentModel)
        mock_existing_agent.id = existing_agent_id
        mock_existing_agent.name = "llama2-uncensored"
        mock_existing_agent.agent_type = AgentTypeEnum.OLLAMA
        mock_existing_agent.endpoint = "http://localhost:11434"
        mock_existing_agent.organization = mock_org_id
        mock_existing_agent.metadata = {}  # existing empty — triggers update

        mock_initial = MagicMock(spec=BackendAgentModel)
        mock_initial.organization = mock_org_id
        mock_initial.owner = 1
        mock_initial.name = "seed_agent"
        mock_agent_list.sync_detailed.side_effect = [
            MagicMock(
                status_code=200, parsed=MagicMock(results=[mock_initial], next=None)
            ),
            MagicMock(
                status_code=200, parsed=MagicMock(results=[mock_initial], next=None)
            ),
            MagicMock(
                status_code=200,
                parsed=MagicMock(results=[mock_existing_agent], next=None),
            ),
        ]

        updated_agent = MagicMock(spec=BackendAgentModel)
        updated_agent.id = existing_agent_id
        updated_agent.name = "llama2-uncensored"
        updated_agent.agent_type = AgentTypeEnum.OLLAMA
        updated_agent.endpoint = "http://localhost:11434"
        updated_agent.metadata = {"name": "llama2-uncensored"}
        updated_agent.organization = mock_org_id

        mock_patch_response = MagicMock()
        mock_patch_response.status_code = 200
        mock_patch_response.parsed = updated_agent
        mock_agent_partial_update.sync_detailed.return_value = mock_patch_response

        metadata_with_nones = {
            "name": "llama2-uncensored",
            "endpoint": "http://localhost:11434",
            "api_key": None,
            "temperature": None,
        }

        _ = AgentRouter(
            client=mock_client,
            name="llama2-uncensored",
            agent_type=AgentTypeEnum.OLLAMA,
            endpoint="http://localhost:11434",
            metadata=metadata_with_nones,
            adapter_operational_config={"name": "llama2-uncensored"},
            overwrite_metadata=True,
        )

        mock_agent_partial_update.sync_detailed.assert_called_once()
        patch_kwargs = mock_agent_partial_update.sync_detailed.call_args[1]
        body = patch_kwargs["body"]

        from hackagent.api.models import PatchedAgentRequest

        self.assertIsInstance(body, PatchedAgentRequest)
        payload = body.model_dump(by_alias=True, mode="json", exclude_none=True)

        if "metadata" in payload:
            sent_metadata = payload["metadata"]
            null_keys = [k for k, v in sent_metadata.items() if v is None]
            self.assertEqual(
                null_keys,
                [],
                f"metadata in PATCH payload must have no null values; found nulls for: {null_keys}",
            )
            self.assertNotIn("api_key", sent_metadata)
            self.assertNotIn("temperature", sent_metadata)


class TestAgentPagination(unittest.TestCase):
    """Regression tests for .next (not .next_) pagination field usage."""

    @patch("hackagent.router.router.agent_list")
    @patch("hackagent.router.router.agent_create")
    @patch("hackagent.router.router.agent_partial_update")
    @patch("hackagent.router.router.LiteLLMAgent", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def test_agent_found_on_page_two_is_not_recreated(
        self,
        MockAgentMap,
        MockLiteLLMAdapter,
        mock_agent_partial_update,
        mock_agent_create,
        mock_agent_list,
    ):
        """When the target agent lives on page 2, it must be found and not re-created."""
        MockAgentMap[AgentTypeEnum.LITELLM] = MockLiteLLMAdapter
        MockLiteLLMAdapter.__name__ = "LiteLLMAgent"

        mock_client = MagicMock(spec=AuthenticatedClient)
        mock_client.token = "test_token"

        mock_org_id = uuid.uuid4()
        mock_user_id = 1

        # An agent on page 1 used for org/user ID retrieval
        org_agent = MagicMock()
        org_agent.organization = mock_org_id
        org_agent.owner = mock_user_id
        org_agent.name = "some_other_agent"
        org_agent.id = uuid.uuid4()

        # The target agent is on page 2
        target_agent = MagicMock()
        target_agent.organization = mock_org_id
        target_agent.owner = mock_user_id
        target_agent.name = "llama2-uncensored"
        target_agent.id = uuid.uuid4()
        target_agent.agent_type = "LITELLM"
        target_agent.endpoint = "http://localhost:11434"
        target_agent.metadata = {"name": "llama2-uncensored"}

        mock_agent_list.sync_detailed.side_effect = [
            # _fetch_organization_id
            MagicMock(
                status_code=200, parsed=MagicMock(results=[org_agent], next=None)
            ),
            # _fetch_user_id_str
            MagicMock(
                status_code=200, parsed=MagicMock(results=[org_agent], next=None)
            ),
            # _find_existing_agent page 1: other agent, next points to page 2
            MagicMock(
                status_code=200,
                parsed=MagicMock(
                    results=[org_agent],
                    next="http://api.example.org/agent/?page=2",
                ),
            ),
            # _find_existing_agent page 2: the target agent, no more pages
            MagicMock(
                status_code=200,
                parsed=MagicMock(results=[target_agent], next=None),
            ),
        ]

        router = AgentRouter(
            client=mock_client,
            name="llama2-uncensored",
            agent_type=AgentTypeEnum.LITELLM,
            endpoint="http://localhost:11434",
            metadata={"name": "llama2-uncensored"},
            adapter_operational_config={"name": "llama2-uncensored"},
            overwrite_metadata=False,
        )

        # Agent was found on page 2 — must NOT call create
        mock_agent_create.sync_detailed.assert_not_called()
        self.assertEqual(router.backend_agent.name, "llama2-uncensored")


if __name__ == "__main__":
    unittest.main()
