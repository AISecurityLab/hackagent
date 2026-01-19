import unittest
import uuid
from unittest.mock import MagicMock, patch

from hackagent.client import AuthenticatedClient
from hackagent.models import Agent as BackendAgentModel

# Assuming AgentTypeEnum and other necessary enums/models are accessible
# We might need to adjust imports based on the actual structure of hackagent.models
from hackagent.router.types import AgentTypeEnum
from hackagent.router.router import AgentRouter


class TestAgentRouterInitialization(unittest.TestCase):
    @patch("hackagent.router.router.agent_list")
    @patch("hackagent.router.router.agent_create")
    @patch("hackagent.router.router.agent_partial_update")
    @patch("hackagent.router.router.LiteLLMAgentAdapter", autospec=True)
    @patch("hackagent.router.router.ADKAgentAdapter", autospec=True)
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

        MockADKAdapter.__name__ = "ADKAgentAdapter"
        MockLiteLLMAdapter.__name__ = "LiteLLMAgentAdapter"

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
                parsed=MagicMock(results=[mock_initial_agent], next_=None),
            ),
            # Second call: _fetch_user_id_str
            MagicMock(
                status_code=200,
                parsed=MagicMock(results=[mock_initial_agent], next_=None),
            ),
            # Third call: _find_existing_agent
            MagicMock(status_code=200, parsed=MagicMock(results=[], next_=None)),
        ]
        mock_agent_list.sync_detailed.side_effect = mock_agent_list_responses

        mock_created_agent_id = uuid.uuid4()
        mock_backend_agent_from_create = MagicMock(spec=BackendAgentModel)
        mock_backend_agent_from_create.id = mock_created_agent_id
        mock_backend_agent_from_create.name = "TestAgent"
        mock_backend_agent_from_create.agent_type = AgentTypeEnum.GOOGLE_ADK
        mock_backend_agent_from_create.endpoint = "http://fake-agent-endpoint.com"
        mock_backend_agent_from_create.metadata = {"initial_meta": "value"}
        mock_backend_agent_from_create.organization = mock_org_id

        mock_agent_create_response = MagicMock()
        mock_agent_create_response.status_code = 201
        mock_agent_create_response.parsed = mock_backend_agent_from_create
        mock_agent_create.sync_detailed.return_value = mock_agent_create_response

        # --- TEST PARAMETERS ---
        agent_name = "TestAgent"
        agent_type = AgentTypeEnum.GOOGLE_ADK
        agent_endpoint = "http://fake-agent-endpoint.com"
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
        self.assertEqual(agent_request_body.endpoint, agent_endpoint)
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
    @patch("hackagent.router.router.LiteLLMAgentAdapter", autospec=True)
    @patch("hackagent.router.router.ADKAgentAdapter", autospec=True)
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
        MockADKAdapter.__name__ = "ADKAgentAdapter"
        MockLiteLLMAdapter.__name__ = "LiteLLMAgentAdapter"

        mock_client = MagicMock(spec=AuthenticatedClient)
        mock_client.token = "test_token_prefix_existing_agent"

        mock_org_id = uuid.uuid4()
        mock_user_id = 456

        agent_name = "ExistingADKAgent"
        agent_type = AgentTypeEnum.GOOGLE_ADK
        agent_endpoint_from_router_init = "http://new-endpoint.com"
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
        mock_agent_list_response.parsed.next_ = None
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
        self.assertEqual(router.backend_agent.endpoint, agent_endpoint_from_router_init)

        expected_registry_key = str(existing_agent_id)
        self.assertIn(expected_registry_key, router._agent_registry)
        self.assertEqual(
            router._agent_registry[expected_registry_key],
            mock_adk_adapter_instance_created,
        )

    @patch("hackagent.router.router.agent_list")
    @patch("hackagent.router.router.agent_create")
    @patch("hackagent.router.router.agent_partial_update")
    @patch("hackagent.router.router.LiteLLMAgentAdapter", autospec=True)
    @patch("hackagent.router.router.ADKAgentAdapter", autospec=True)
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
        MockADKAdapter.__name__ = "ADKAgentAdapter"
        # MockLiteLLMAdapter not used in this specific ADK test but keep for consistency
        MockLiteLLMAdapter.__name__ = "LiteLLMAgentAdapter"

        mock_client = MagicMock(spec=AuthenticatedClient)
        mock_client.token = "test_token_metadata_m_atch_suffix"

        mock_org_id = uuid.uuid4()
        mock_user_id = 789

        agent_name = "ADKAgentMetaMatch"
        agent_type = AgentTypeEnum.GOOGLE_ADK
        # Metadata and endpoint that will be passed to AgentRouter init
        # and will be mocked as already existing in the backend.
        current_metadata = {"feature_flag": True, "version": "1.0.0"}
        current_endpoint = "http://current-endpoint.com"
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
        mock_agent_list_response.parsed.next_ = None
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
        self.assertEqual(router.backend_agent.endpoint, current_endpoint)

        expected_registry_key = str(existing_agent_id)
        self.assertIn(expected_registry_key, router._agent_registry)
        self.assertEqual(
            router._agent_registry[expected_registry_key],
            mock_adk_adapter_instance_created,
        )

    @patch("hackagent.router.router.agent_list")
    @patch("hackagent.router.router.agent_create")
    @patch("hackagent.router.router.agent_partial_update")
    @patch("hackagent.router.router.LiteLLMAgentAdapter", autospec=True)
    @patch("hackagent.router.router.ADKAgentAdapter", autospec=True)
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
        MockADKAdapter.__name__ = "ADKAgentAdapter"
        MockLiteLLMAdapter.__name__ = "LiteLLMAgentAdapter"

        mock_client = MagicMock(spec=AuthenticatedClient)
        mock_client.token = "test_token_meta_match_overwrite_false"

        mock_org_id = uuid.uuid4()
        mock_user_id = 101112

        agent_name = "ADKAgentMetaMatchOverwriteFalse"
        agent_type = AgentTypeEnum.GOOGLE_ADK
        current_metadata = {"feature_flag": True, "version": "1.0.1"}
        current_endpoint = "http://current-endpoint-ow-false.com"
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
        mock_agent_list_response.parsed.next_ = None
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
        self.assertEqual(router.backend_agent.endpoint, current_endpoint)

        expected_registry_key = str(existing_agent_id)
        self.assertIn(expected_registry_key, router._agent_registry)
        self.assertEqual(
            router._agent_registry[expected_registry_key],
            mock_adk_adapter_instance_created,
        )

    @patch("hackagent.router.router.agent_list")
    @patch("hackagent.router.router.agent_create")
    @patch("hackagent.router.router.agent_partial_update")
    @patch("hackagent.router.router.LiteLLMAgentAdapter", autospec=True)
    @patch("hackagent.router.router.ADKAgentAdapter", autospec=True)
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
        MockADKAdapter.__name__ = "ADKAgentAdapter"
        MockLiteLLMAdapter.__name__ = "LiteLLMAgentAdapter"

        mock_client = MagicMock(spec=AuthenticatedClient)
        mock_client.token = "test_token_diff_meta_ow_false"
        mock_org_id = uuid.uuid4()
        mock_user_id = 654

        agent_name = "ExistingADKAgentDiffMetaOverwriteFalse"
        agent_type = AgentTypeEnum.GOOGLE_ADK

        # Metadata for AgentRouter init (DIFFERENT from existing)
        router_init_endpoint = "http://new-endpoint-for-router.com"
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
                parsed=MagicMock(results=[mock_initial_agent], next_=None),
            ),
            MagicMock(
                status_code=200,
                parsed=MagicMock(results=[mock_initial_agent], next_=None),
            ),
            MagicMock(
                status_code=200,
                parsed=MagicMock(results=[existing_agent_mock], next_=None),
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
    @patch("hackagent.router.router.LiteLLMAgentAdapter", autospec=True)
    @patch("hackagent.router.router.ADKAgentAdapter", autospec=True)
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
        MockADKAdapter.__name__ = "ADKAgentAdapter"
        MockLiteLLMAdapter.__name__ = "LiteLLMAgentAdapter"

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
                parsed=MagicMock(results=[mock_initial_agent], next_=None),
            ),
            # Second call: _fetch_user_id_str
            MagicMock(
                status_code=200,
                parsed=MagicMock(results=[mock_initial_agent], next_=None),
            ),
            # Third call: _find_existing_agent
            MagicMock(status_code=200, parsed=MagicMock(results=[], next_=None)),
        ]
        mock_agent_list.sync_detailed.side_effect = mock_agent_list_responses

        # Mock agent_create response
        created_litellm_agent_id = uuid.uuid4()
        mock_backend_agent_from_create = MagicMock(spec=BackendAgentModel)
        mock_backend_agent_from_create.id = created_litellm_agent_id
        mock_backend_agent_from_create.name = "TestLiteLLMAgent"
        mock_backend_agent_from_create.agent_type = AgentTypeEnum.LITELLM
        mock_backend_agent_from_create.endpoint = (
            "http://litellm-router-endpoint.com"  # Endpoint for router registration
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
        agent_endpoint_param = "http://litellm-router-endpoint.com"
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
        self.assertEqual(agent_request_body.endpoint, agent_endpoint_param)
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
            "endpoint": "http://litellm-router-endpoint.com",  # From backend_agent.endpoint
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


class TestAgentRouterRouteWithTracking(unittest.TestCase):
    """Test route_with_tracking method."""

    @patch("hackagent.router.router.agent_list")
    @patch("hackagent.router.router.agent_create")
    @patch("hackagent.router.router.LiteLLMAgentAdapter", autospec=True)
    @patch("hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP", new_callable=dict)
    def setUp(
        self,
        MockAgentMap,
        MockLiteLLMAdapter,
        mock_agent_create,
        mock_agent_list,
    ):
        """Set up router with mocked dependencies."""
        MockAgentMap[AgentTypeEnum.LITELLM] = MockLiteLLMAdapter
        MockLiteLLMAdapter.__name__ = "LiteLLMAgentAdapter"

        self.mock_client = MagicMock(spec=AuthenticatedClient)
        self.mock_client.token = "test_token_prefix_12345"

        mock_org_id = uuid.uuid4()
        mock_user_id = 123

        mock_initial_agent = MagicMock(spec=BackendAgentModel)
        mock_initial_agent.organization = mock_org_id
        mock_initial_agent.owner = mock_user_id

        mock_agent_list_responses = [
            MagicMock(
                status_code=200,
                parsed=MagicMock(results=[mock_initial_agent], next_=None),
            ),
            MagicMock(
                status_code=200,
                parsed=MagicMock(results=[mock_initial_agent], next_=None),
            ),
            MagicMock(status_code=200, parsed=MagicMock(results=[], next_=None)),
        ]
        mock_agent_list.sync_detailed.side_effect = mock_agent_list_responses

        self.mock_agent_id = uuid.uuid4()
        mock_backend_agent = MagicMock(spec=BackendAgentModel)
        mock_backend_agent.id = self.mock_agent_id
        mock_backend_agent.name = "TestAgent"
        mock_backend_agent.agent_type = AgentTypeEnum.LITELLM
        mock_backend_agent.endpoint = "http://test.com"
        mock_backend_agent.metadata = {"name": "test-model"}
        mock_backend_agent.organization = mock_org_id

        mock_agent_create_response = MagicMock()
        mock_agent_create_response.status_code = 201
        mock_agent_create_response.parsed = mock_backend_agent
        mock_agent_create.sync_detailed.return_value = mock_agent_create_response

        # Mock the adapter
        self.mock_adapter = MagicMock()
        MockLiteLLMAdapter.return_value = self.mock_adapter

        self.router = AgentRouter(
            client=self.mock_client,
            name="TestAgent",
            agent_type=AgentTypeEnum.LITELLM,
            endpoint="http://test.com",
            metadata={"name": "test-model"},
        )

    @patch("hackagent.api.run.run_result_create.sync_detailed")
    def test_route_with_tracking_creates_result(self, mock_result_create):
        """Test that route_with_tracking creates a Result record."""
        # Setup adapter response
        self.mock_adapter.handle_request.return_value = {"response": "test response"}

        # Setup result create response
        mock_result_response = MagicMock()
        mock_result_response.status_code = 201
        mock_result_response.parsed = MagicMock(id=uuid.uuid4())
        mock_result_create.return_value = mock_result_response

        run_id = str(uuid.uuid4())
        registration_key = str(self.mock_agent_id)

        response = self.router.route_with_tracking(
            registration_key=registration_key,
            request_data={"prompt": "test"},
            run_id=run_id,
            client=self.mock_client,
        )

        # Verify adapter was called
        self.mock_adapter.handle_request.assert_called_once()

        # Verify result was created
        mock_result_create.assert_called_once()

        # Verify response structure includes both response and result_id
        self.assertIn("response", response)
        self.assertIn("result_id", response)
        self.assertEqual(response["response"], {"response": "test response"})

    @patch("hackagent.api.run.run_result_create.sync_detailed")
    def test_route_with_tracking_handles_result_creation_failure(
        self, mock_result_create
    ):
        """Test route_with_tracking handles result creation failure gracefully."""
        # Setup adapter response
        self.mock_adapter.handle_request.return_value = {"response": "test response"}

        # Setup result create to fail
        mock_result_response = MagicMock()
        mock_result_response.status_code = 500
        mock_result_create.return_value = mock_result_response

        run_id = str(uuid.uuid4())
        registration_key = str(self.mock_agent_id)

        # Should not raise, just log warning
        response = self.router.route_with_tracking(
            registration_key=registration_key,
            request_data={"prompt": "test"},
            run_id=run_id,
            client=self.mock_client,
        )

        # Response should still be returned with None result_id
        self.assertEqual(response["response"], {"response": "test response"})
        self.assertIsNone(response["result_id"])

    @patch("hackagent.api.run.run_result_create.sync_detailed")
    def test_route_with_tracking_handles_exception(self, mock_result_create):
        """Test route_with_tracking handles exceptions during result creation."""
        # Setup adapter response
        self.mock_adapter.handle_request.return_value = {"response": "test response"}

        # Setup result create to raise exception
        mock_result_create.side_effect = Exception("API Error")

        run_id = str(uuid.uuid4())
        registration_key = str(self.mock_agent_id)

        # Should not raise, just log error
        response = self.router.route_with_tracking(
            registration_key=registration_key,
            request_data={"prompt": "test"},
            run_id=run_id,
            client=self.mock_client,
        )

        # Response should still be returned with None result_id
        self.assertEqual(response["response"], {"response": "test response"})
        self.assertIsNone(response["result_id"])

    @patch("hackagent.api.run.run_result_create.sync_detailed")
    def test_route_with_tracking_with_custom_evaluation_status(
        self, mock_result_create
    ):
        """Test route_with_tracking with custom evaluation status."""
        from hackagent.models import EvaluationStatusEnum

        # Setup adapter response
        self.mock_adapter.handle_request.return_value = {"response": "test"}

        # Setup result create response
        mock_result_response = MagicMock()
        mock_result_response.status_code = 201
        mock_result_response.parsed = MagicMock(id=uuid.uuid4())
        mock_result_create.return_value = mock_result_response

        run_id = str(uuid.uuid4())
        registration_key = str(self.mock_agent_id)

        self.router.route_with_tracking(
            registration_key=registration_key,
            request_data={"prompt": "test"},
            run_id=run_id,
            client=self.mock_client,
            evaluation_status=EvaluationStatusEnum.PASSED_CRITERIA,
        )

        # Verify the evaluation status was passed
        call_args = mock_result_create.call_args
        body = call_args.kwargs["body"]
        self.assertEqual(body.evaluation_status, EvaluationStatusEnum.PASSED_CRITERIA)


if __name__ == "__main__":
    unittest.main()
