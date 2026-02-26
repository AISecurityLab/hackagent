# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest
import uuid  # For generating mock UUIDs
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from hackagent import errors
from hackagent.api.agent import (
    agent_create,
    agent_destroy,
    agent_list,
    agent_partial_update,
    agent_retrieve,
    agent_update,
)  # Added agent_partial_update
from hackagent.router.types import AgentTypeEnum  # For AgentRequest body
from hackagent.api.models import (
    Agent,
)  # For agent_create, agent_retrieve, agent_update
from hackagent.api.models import (
    AgentRequest,
)  # For agent_create, agent_update

# Assuming these are the correct import paths based on the project structure
from hackagent.api.models import PaginatedAgentList
from hackagent.api.models import (
    PatchedAgentRequest,
)  # For agent_partial_update
from hackagent.types import UNSET  # Alias to avoid conflict, import UNSET


class TestAgentListAPI(unittest.TestCase):
    @patch("hackagent.api.agent.agent_list.AuthenticatedClient")
    def test_agent_list_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        mock_agent_id = str(uuid.uuid4())
        mock_org_id = str(uuid.uuid4())
        mock_agent_data = {
            "id": mock_agent_id,
            "name": "Test Agent",
            "endpoint": "http://example.com/agent",
            "agent_type": AgentTypeEnum.GOOGLE_ADK.value,
            "organization": mock_org_id,
            "organization_detail": {
                "id": mock_org_id,
                "name": "Test Org",
            },  # Added organization_detail
            "owner": None,
            "owner_detail": None,
            "metadata": None,
            "description": "A test agent",
            "created_at": "2023-01-01T12:00:00Z",
            "updated_at": "2023-01-01T12:00:00Z",
            "is_public": False,
            "is_active": True,
        }
        mock_response_content = {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [mock_agent_data],
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 200
        mock_httpx_response.json.return_value = mock_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_object = PaginatedAgentList.model_validate(mock_response_content)

        with patch(
            "hackagent.api.agent.agent_list.PaginatedAgentList.model_validate",
            return_value=mock_parsed_object,
        ) as mock_model_validate:
            response = agent_list.sync_detailed(client=mock_client_instance, page=1)

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.count, 1)
            # Ensure results is a list and has elements before accessing
            self.assertTrue(
                isinstance(response.parsed.results, list)
                and len(response.parsed.results) > 0
            )
            self.assertEqual(str(response.parsed.results[0].id), mock_agent_id)
            mock_model_validate.assert_called_once_with(mock_response_content)

            expected_kwargs = {
                "method": "get",
                "url": "/agent",
                "params": {"page": 1},
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.agent.agent_list.AuthenticatedClient")
    def test_agent_list_sync_detailed_error_raise_on_unexpected_status_true(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 500
        mock_httpx_response.content = b"Server Error"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            agent_list.sync_detailed(client=mock_client_instance)

        self.assertEqual(cm.exception.status_code, 500)
        self.assertEqual(cm.exception.content, b"Server Error")

    @patch("hackagent.api.agent.agent_list.AuthenticatedClient")
    def test_agent_list_sync_detailed_error_raise_on_unexpected_status_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 403
        mock_httpx_response.content = b"Forbidden"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = agent_list.sync_detailed(client=mock_client_instance)

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIsNone(response.parsed)


class TestAgentCreateAPI(unittest.TestCase):
    @patch("hackagent.api.agent.agent_create.AuthenticatedClient")
    def test_agent_create_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        agent_id_for_request = uuid.uuid4()
        agent_request_data = AgentRequest(
            name="New Test Agent",
            agent_type=AgentTypeEnum.GOOGLE_ADK.value,
            endpoint="http://example.com/adk",
        )

        mock_created_agent_id = uuid.uuid4()
        mock_response_content = {
            "id": str(mock_created_agent_id),
            "name": agent_request_data.name,
            "agent_type": agent_request_data.agent_type,
            "endpoint": agent_request_data.endpoint,
            "organization": str(agent_id_for_request),
            "organization_detail": {
                "id": str(agent_id_for_request),
                "name": "Test Org Detail",
            },
            "owner": None,
            "owner_detail": None,
            "metadata": None,
            "description": None,
            "created_at": "2023-01-01T12:00:00Z",
            "updated_at": "2023-01-01T12:00:00Z",
            "is_public": False,
            "is_active": True,
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 201
        mock_httpx_response.json.return_value = mock_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_agent = Agent.model_validate(mock_response_content)

        with patch(
            "hackagent.api.agent.agent_create.Agent.model_validate",
            return_value=mock_parsed_agent,
        ) as mock_model_validate:
            response = agent_create.sync_detailed(
                client=mock_client_instance, body=agent_request_data
            )

            self.assertEqual(response.status_code, HTTPStatus.CREATED)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.id, mock_created_agent_id)
            self.assertEqual(response.parsed.name, agent_request_data.name)
            mock_model_validate.assert_called_once_with(mock_response_content)

            expected_kwargs = {
                "method": "post",
                "url": "/agent",
                "json": agent_request_data.model_dump(by_alias=True, mode="json", exclude_none=True),
                "headers": {"Content-Type": "application/json"},
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.agent.agent_create.AuthenticatedClient")
    def test_agent_create_sync_detailed_error_raise_on_unexpected_status_true(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        agent_request_data = AgentRequest(
            name="Error Agent",
            agent_type=AgentTypeEnum.GOOGLE_ADK.value,
            endpoint="http://error-test.example.com",
        )

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 400
        mock_httpx_response.content = b"Bad Request Data"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            agent_create.sync_detailed(
                client=mock_client_instance, body=agent_request_data
            )

        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(cm.exception.content, b"Bad Request Data")

    @patch("hackagent.api.agent.agent_create.AuthenticatedClient")
    def test_agent_create_sync_detailed_error_raise_on_unexpected_status_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        agent_request_data = AgentRequest(
            name="Error Agent False",
            agent_type=AgentTypeEnum.GOOGLE_ADK.value,
            endpoint="http://error-false-test.example.com",
        )

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 401
        mock_httpx_response.content = b"Unauthorized Access"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = agent_create.sync_detailed(
            client=mock_client_instance, body=agent_request_data
        )

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
        self.assertIsNone(response.parsed)


class TestAgentRetrieveAPI(unittest.TestCase):
    @patch("hackagent.api.agent.agent_retrieve.AuthenticatedClient")
    def test_agent_retrieve_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        agent_id_to_retrieve = uuid.uuid4()
        mock_response_content = {
            "id": str(agent_id_to_retrieve),
            "name": "Retrieved Agent",
            "agent_type": AgentTypeEnum.LITELLM.value,
            "endpoint": "http://example.com/retrieved",
            "organization": str(uuid.uuid4()),
            "organization_detail": {
                "id": str(uuid.uuid4()),
                "name": "Test Org Detail Retrieve",
            },
            "owner": None,
            "owner_detail": None,
            "metadata": None,
            "description": "A retrieved agent.",
            "created_at": "2023-01-02T10:00:00Z",
            "updated_at": "2023-01-02T11:00:00Z",
            "is_public": True,
            "is_active": True,
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 200
        mock_httpx_response.json.return_value = mock_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_agent = Agent.model_validate(mock_response_content)

        with patch(
            "hackagent.api.agent.agent_retrieve.Agent.model_validate",
            return_value=mock_parsed_agent,
        ) as mock_model_validate:
            response = agent_retrieve.sync_detailed(
                client=mock_client_instance, id=agent_id_to_retrieve
            )

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.id, agent_id_to_retrieve)
            self.assertEqual(response.parsed.name, "Retrieved Agent")
            mock_model_validate.assert_called_once_with(mock_response_content)

            expected_kwargs = {
                "method": "get",
                "url": f"/agent/{agent_id_to_retrieve}",
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.agent.agent_retrieve.AuthenticatedClient")
    def test_agent_retrieve_sync_detailed_error_not_found(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        agent_id_not_found = uuid.uuid4()
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 404
        mock_httpx_response.content = b"Agent Not Found"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            agent_retrieve.sync_detailed(
                client=mock_client_instance, id=agent_id_not_found
            )

        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.content, b"Agent Not Found")

    @patch("hackagent.api.agent.agent_retrieve.AuthenticatedClient")
    def test_agent_retrieve_sync_detailed_error_raise_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        agent_id_error = uuid.uuid4()
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 500  # Internal Server Error
        mock_httpx_response.content = b"Server Side Issue"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = agent_retrieve.sync_detailed(
            client=mock_client_instance, id=agent_id_error
        )

        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.assertIsNone(response.parsed)


class TestAgentUpdateAPI(unittest.TestCase):
    @patch("hackagent.api.agent.agent_update.AuthenticatedClient")
    def test_agent_update_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        agent_id_to_update = uuid.uuid4()
        agent_update_request_data = AgentRequest(
            name="Updated Test Agent",
            agent_type=AgentTypeEnum.LITELLM.value,
            endpoint="http://example.com/updated-litellm",
            description="Updated description",
        )

        mock_org_id_update = str(uuid.uuid4())  # Generate mock org ID for response
        mock_updated_agent_response_content = {
            "id": str(agent_id_to_update),
            "name": agent_update_request_data.name,
            "agent_type": agent_update_request_data.agent_type,
            "endpoint": agent_update_request_data.endpoint,
            "organization": mock_org_id_update,
            "organization_detail": {
                "id": mock_org_id_update,
                "name": "Updated Org Detail",
            },
            "owner": None,
            "owner_detail": None,
            "metadata": None,
            "description": agent_update_request_data.description,
            "created_at": "2023-01-01T12:00:00Z",
            "updated_at": "2023-01-03T10:00:00Z",  # Updated time
            "is_public": False,
            "is_active": True,
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 200  # OK for update
        mock_httpx_response.json.return_value = mock_updated_agent_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_agent = Agent.model_validate(mock_updated_agent_response_content)

        with patch(
            "hackagent.api.agent.agent_update.Agent.model_validate",
            return_value=mock_parsed_agent,
        ) as mock_model_validate:
            response = agent_update.sync_detailed(
                client=mock_client_instance,
                id=agent_id_to_update,
                body=agent_update_request_data,
            )

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.id, agent_id_to_update)
            self.assertEqual(response.parsed.name, agent_update_request_data.name)
            self.assertEqual(
                response.parsed.description, agent_update_request_data.description
            )
            mock_model_validate.assert_called_once_with(mock_updated_agent_response_content)

            expected_kwargs = {
                "method": "put",
                "url": f"/agent/{agent_id_to_update}",
                "json": agent_update_request_data.model_dump(by_alias=True, mode="json", exclude_none=True),
                "headers": {"Content-Type": "application/json"},
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.agent.agent_update.AuthenticatedClient")
    def test_agent_update_sync_detailed_error_not_found(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        agent_id_not_found = uuid.uuid4()
        agent_update_request_data = AgentRequest(
            name="NonExistent Update",
            agent_type=AgentTypeEnum.GOOGLE_ADK.value,
            endpoint="http://error-test.example.com",
        )

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 404
        mock_httpx_response.content = b"Agent Not Found For Update"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            agent_update.sync_detailed(
                client=mock_client_instance,
                id=agent_id_not_found,
                body=agent_update_request_data,
            )

        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.content, b"Agent Not Found For Update")

    @patch("hackagent.api.agent.agent_update.AuthenticatedClient")
    def test_agent_update_sync_detailed_error_raise_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        agent_id_error = uuid.uuid4()
        agent_update_request_data = AgentRequest(
            name="Update Error False",
            agent_type=AgentTypeEnum.LITELLM.value,
            endpoint="http://error-false-test.example.com",
        )

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 400  # Bad Request for example
        mock_httpx_response.content = b"Invalid Update Data"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = agent_update.sync_detailed(
            client=mock_client_instance,
            id=agent_id_error,
            body=agent_update_request_data,
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIsNone(response.parsed)


class TestAgentDestroyAPI(unittest.TestCase):
    @patch("hackagent.api.agent.agent_destroy.AuthenticatedClient")
    def test_agent_destroy_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        agent_id_to_delete = uuid.uuid4()

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 204  # No Content for successful deletion
        mock_httpx_response.content = b""  # No content
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = agent_destroy.sync_detailed(
            client=mock_client_instance, id=agent_id_to_delete
        )

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        self.assertIsNone(response.parsed)  # No parsed content for 204

        expected_kwargs = {
            "method": "delete",
            "url": f"/agent/{agent_id_to_delete}",
        }
        mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.agent.agent_destroy.AuthenticatedClient")
    def test_agent_destroy_sync_detailed_error_not_found(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        agent_id_not_found = uuid.uuid4()

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 404
        mock_httpx_response.content = b"Agent Not Found For Deletion"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            agent_destroy.sync_detailed(
                client=mock_client_instance, id=agent_id_not_found
            )

        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.content, b"Agent Not Found For Deletion")

    @patch("hackagent.api.agent.agent_destroy.AuthenticatedClient")
    def test_agent_destroy_sync_detailed_error_raise_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        agent_id_error = uuid.uuid4()

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 500  # Internal Server Error
        mock_httpx_response.content = b"Deletion Failed Server Side"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = agent_destroy.sync_detailed(
            client=mock_client_instance, id=agent_id_error
        )

        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.assertIsNone(response.parsed)


class TestAgentPartialUpdateAPI(unittest.TestCase):
    @patch("hackagent.api.agent.agent_partial_update.AuthenticatedClient")
    def test_agent_partial_update_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        agent_id_to_patch = uuid.uuid4()
        agent_patch_request_data = PatchedAgentRequest(
            description="Partially updated description"
        )

        mock_org_id_patch = str(uuid.uuid4())
        mock_patched_agent_response_content = {
            "id": str(agent_id_to_patch),
            "name": "Existing Agent Name",
            "agent_type": AgentTypeEnum.GOOGLE_ADK.value,
            "endpoint": "http://example.com/existing-adk",
            "organization": mock_org_id_patch,
            "organization_detail": {
                "id": mock_org_id_patch,
                "name": "Patched Org Detail",
            },
            "owner": None,
            "owner_detail": None,
            "metadata": {"info": "original metadata"},
            "description": agent_patch_request_data.description,
            "created_at": "2023-01-01T12:00:00Z",
            "updated_at": "2023-01-04T10:00:00Z",
            "is_public": False,
            "is_active": True,
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 200  # OK for partial update
        mock_httpx_response.json.return_value = mock_patched_agent_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_agent = Agent.model_validate(mock_patched_agent_response_content)

        with patch(
            "hackagent.api.agent.agent_partial_update.Agent.model_validate",
            return_value=mock_parsed_agent,
        ) as mock_model_validate:
            response = agent_partial_update.sync_detailed(
                client=mock_client_instance,
                id=agent_id_to_patch,
                body=agent_patch_request_data,
            )

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.id, agent_id_to_patch)
            self.assertEqual(
                response.parsed.description, agent_patch_request_data.description
            )
            mock_model_validate.assert_called_once_with(mock_patched_agent_response_content)

            expected_kwargs = {
                "method": "patch",
                "url": f"/agent/{agent_id_to_patch}",
                "json": agent_patch_request_data.model_dump(by_alias=True, mode="json", exclude_none=True),
                "headers": {"Content-Type": "application/json"},
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.agent.agent_partial_update.AuthenticatedClient")
    def test_agent_partial_update_sync_detailed_error_not_found(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        agent_id_not_found = uuid.uuid4()
        agent_patch_request_data = PatchedAgentRequest(name="NonExistent Patch")

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 404
        mock_httpx_response.content = b"Agent Not Found For Patch"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            agent_partial_update.sync_detailed(
                client=mock_client_instance,
                id=agent_id_not_found,
                body=agent_patch_request_data,
            )

        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.content, b"Agent Not Found For Patch")

    @patch("hackagent.api.agent.agent_partial_update.AuthenticatedClient")
    def test_agent_partial_update_sync_detailed_error_raise_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        agent_id_error = uuid.uuid4()
        agent_patch_request_data = PatchedAgentRequest(endpoint="http://invalid.example.com/url/for/patch")

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 400  # Bad Request for example
        mock_httpx_response.content = b"Invalid Patch Data"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = agent_partial_update.sync_detailed(
            client=mock_client_instance,
            id=agent_id_error,
            body=agent_patch_request_data,
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIsNone(response.parsed)


if __name__ == "__main__":
    unittest.main()
