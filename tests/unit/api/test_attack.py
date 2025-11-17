# Copyright 2025 - AI4I. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import unittest
from unittest.mock import patch, MagicMock
from http import HTTPStatus
import uuid
import datetime  # Added for datetime objects

# Assuming these are the correct import paths based on the project structure
from hackagent.models.paginated_attack_list import PaginatedAttackList
from hackagent.models.attack import Attack  # For individual attack items
from hackagent.api.attack import (
    attack_list,
    attack_create,
    attack_retrieve,
    attack_update,
    attack_partial_update,
    attack_destroy,
)
from hackagent import errors
from hackagent.models.attack_request import AttackRequest
from hackagent.models.patched_attack_request import (
    PatchedAttackRequest,
)  # Added PatchedAttackRequest


class TestAttackListAPI(unittest.TestCase):
    @patch("hackagent.api.attack.attack_list.AuthenticatedClient")
    def test_attack_list_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        mock_attack_id = uuid.uuid4()
        mock_agent_id = uuid.uuid4()
        mock_org_id = uuid.uuid4()

        # Timestamps need to be in ISO format string for the mock response content,
        # but datetime objects for the Attack model instance if we were creating one directly.
        # For from_dict, string format is expected in the dictionary.
        created_at_str = "2023-01-01T10:00:00Z"
        updated_at_str = "2023-01-01T11:00:00Z"

        mock_attack_data = {
            "id": str(mock_attack_id),
            "type": "PREFIX_GENERATION",
            "agent": str(mock_agent_id),
            "agent_name": "Test Agent for Attack",
            "owner": 1,  # Assuming owner is an int ID
            "owner_username": "testuser",
            "organization": str(mock_org_id),
            "organization_name": "Test Org for Attack",
            "configuration": {"param1": "value1"},
            "created_at": created_at_str,
            "updated_at": updated_at_str,
        }
        mock_response_content = {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [mock_attack_data],
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 200
        mock_httpx_response.json.return_value = mock_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        # Create a PaginatedAttackList instance from the mock content
        # This helps ensure our mock_response_content matches the model's expectations
        mock_parsed_object = PaginatedAttackList.from_dict(mock_response_content)

        with patch(
            "hackagent.api.attack.attack_list.PaginatedAttackList.from_dict",
            return_value=mock_parsed_object,
        ) as mock_from_dict:
            response = attack_list.sync_detailed(client=mock_client_instance, page=1)

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.count, 1)
            self.assertTrue(
                isinstance(response.parsed.results, list)
                and len(response.parsed.results) > 0
            )

            # Access the first Attack object in the results
            retrieved_attack = response.parsed.results[0]
            self.assertEqual(retrieved_attack.id, mock_attack_id)
            self.assertEqual(retrieved_attack.type_, "PREFIX_GENERATION")
            # We can also check datetime objects if from_dict correctly parses them
            self.assertEqual(
                retrieved_attack.created_at,
                datetime.datetime.fromisoformat(created_at_str.replace("Z", "+00:00")),
            )

            mock_from_dict.assert_called_once_with(mock_response_content)

            expected_kwargs = {
                "method": "get",
                "url": "/api/attack",
                "params": {"page": 1},
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.attack.attack_list.AuthenticatedClient")
    def test_attack_list_sync_detailed_error_raise_on_unexpected_status_true(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 500
        mock_httpx_response.content = b"Server Error For Attack List"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            attack_list.sync_detailed(client=mock_client_instance)

        self.assertEqual(cm.exception.status_code, 500)
        self.assertEqual(cm.exception.content, b"Server Error For Attack List")

    @patch("hackagent.api.attack.attack_list.AuthenticatedClient")
    def test_attack_list_sync_detailed_error_raise_on_unexpected_status_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 403  # Forbidden
        mock_httpx_response.content = b"Forbidden Access to Attack List"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = attack_list.sync_detailed(client=mock_client_instance)

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIsNone(response.parsed)


class TestAttackCreateAPI(unittest.TestCase):
    @patch("hackagent.api.attack.attack_create.AuthenticatedClient")
    def test_attack_create_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        mock_agent_id = uuid.uuid4()
        attack_request_data = AttackRequest(
            type_="PROMPT_INJECTION",
            agent=mock_agent_id,
            configuration={"level": 5, "target": "user_data"},
        )

        mock_created_attack_id = uuid.uuid4()
        mock_org_id_create = (
            uuid.uuid4()
        )  # Separate org_id for this specific response mock
        created_at_str = "2023-02-01T10:00:00Z"
        updated_at_str = "2023-02-01T11:00:00Z"

        mock_response_content = {
            "id": str(mock_created_attack_id),
            "type": attack_request_data.type_,
            "agent": str(attack_request_data.agent),
            "agent_name": "Agent For Created Attack",
            "owner": 2,  # Mock owner ID
            "owner_username": "creator_user",
            "organization": str(mock_org_id_create),
            "organization_name": "Org For Created Attack",
            "configuration": attack_request_data.configuration,
            "created_at": created_at_str,
            "updated_at": updated_at_str,
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 201  # Created
        mock_httpx_response.json.return_value = mock_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_attack = Attack.from_dict(mock_response_content)

        with patch(
            "hackagent.api.attack.attack_create.Attack.from_dict",
            return_value=mock_parsed_attack,
        ) as mock_from_dict:
            response = attack_create.sync_detailed(
                client=mock_client_instance, body=attack_request_data
            )

            self.assertEqual(response.status_code, HTTPStatus.CREATED)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.id, mock_created_attack_id)
            self.assertEqual(response.parsed.type_, attack_request_data.type_)
            self.assertEqual(response.parsed.agent, attack_request_data.agent)
            self.assertEqual(
                response.parsed.configuration, attack_request_data.configuration
            )
            mock_from_dict.assert_called_once_with(mock_response_content)

            expected_kwargs = {
                "method": "post",
                "url": "/api/attack",
                "json": attack_request_data.to_dict(),
                "headers": {"Content-Type": "application/json"},
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.attack.attack_create.AuthenticatedClient")
    def test_attack_create_sync_detailed_error_raise_on_unexpected_status_true(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        attack_request_data = AttackRequest(
            type_="ERROR_CASE", agent=uuid.uuid4(), configuration={}
        )

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 400
        mock_httpx_response.content = b"Bad Attack Request Data"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            attack_create.sync_detailed(
                client=mock_client_instance, body=attack_request_data
            )

        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(cm.exception.content, b"Bad Attack Request Data")

    @patch("hackagent.api.attack.attack_create.AuthenticatedClient")
    def test_attack_create_sync_detailed_error_raise_on_unexpected_status_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        attack_request_data = AttackRequest(
            type_="ERROR_FALSE_CASE", agent=uuid.uuid4(), configuration={}
        )

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 401
        mock_httpx_response.content = b"Unauthorized Attack Creation"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = attack_create.sync_detailed(
            client=mock_client_instance, body=attack_request_data
        )

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
        self.assertIsNone(response.parsed)


class TestAttackRetrieveAPI(unittest.TestCase):
    @patch("hackagent.api.attack.attack_retrieve.AuthenticatedClient")
    def test_attack_retrieve_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        attack_id_to_retrieve = uuid.uuid4()
        mock_agent_id_retrieve = uuid.uuid4()
        mock_org_id_retrieve = uuid.uuid4()
        created_at_str = "2023-03-01T10:00:00Z"
        updated_at_str = "2023-03-01T11:00:00Z"

        mock_response_content = {
            "id": str(attack_id_to_retrieve),
            "type": "SQL_INJECTION",
            "agent": str(mock_agent_id_retrieve),
            "agent_name": "Retrieved Agent for Attack",
            "owner": 3,
            "owner_username": "retriever_user",
            "organization": str(mock_org_id_retrieve),
            "organization_name": "Org For Retrieved Attack",
            "configuration": {"db_type": "postgres"},
            "created_at": created_at_str,
            "updated_at": updated_at_str,
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 200
        mock_httpx_response.json.return_value = mock_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_attack = Attack.from_dict(mock_response_content)

        with patch(
            "hackagent.api.attack.attack_retrieve.Attack.from_dict",
            return_value=mock_parsed_attack,
        ) as mock_from_dict:
            response = attack_retrieve.sync_detailed(
                client=mock_client_instance, id=attack_id_to_retrieve
            )

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.id, attack_id_to_retrieve)
            self.assertEqual(response.parsed.type_, "SQL_INJECTION")
            self.assertEqual(
                response.parsed.created_at,
                datetime.datetime.fromisoformat(created_at_str.replace("Z", "+00:00")),
            )
            mock_from_dict.assert_called_once_with(mock_response_content)

            expected_kwargs = {
                "method": "get",
                "url": f"/api/attack/{attack_id_to_retrieve}",
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.attack.attack_retrieve.AuthenticatedClient")
    def test_attack_retrieve_sync_detailed_error_not_found(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        attack_id_not_found = uuid.uuid4()
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 404
        mock_httpx_response.content = b"Attack Not Found"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            attack_retrieve.sync_detailed(
                client=mock_client_instance, id=attack_id_not_found
            )

        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.content, b"Attack Not Found")

    @patch("hackagent.api.attack.attack_retrieve.AuthenticatedClient")
    def test_attack_retrieve_sync_detailed_error_raise_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        attack_id_error = uuid.uuid4()
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 500
        mock_httpx_response.content = b"Server Side Issue For Retrieve"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = attack_retrieve.sync_detailed(
            client=mock_client_instance, id=attack_id_error
        )

        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.assertIsNone(response.parsed)


class TestAttackUpdateAPI(unittest.TestCase):
    @patch("hackagent.api.attack.attack_update.AuthenticatedClient")
    def test_attack_update_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        attack_id_to_update = uuid.uuid4()
        mock_agent_id_update = uuid.uuid4()

        attack_update_request_data = AttackRequest(
            type_="XSS_ATTACK",
            agent=mock_agent_id_update,
            configuration={"payload": "<script>alert(1)</script>"},
        )

        mock_org_id_update = uuid.uuid4()
        created_at_str = "2023-04-01T10:00:00Z"
        # Ensure updated_at is different from created_at for an update
        updated_at_str = "2023-04-01T12:00:00Z"

        mock_updated_attack_response_content = {
            "id": str(attack_id_to_update),
            "type": attack_update_request_data.type_,
            "agent": str(attack_update_request_data.agent),
            "agent_name": "Agent For Updated Attack",
            "owner": 4,
            "owner_username": "updater_user",
            "organization": str(mock_org_id_update),
            "organization_name": "Org For Updated Attack",
            "configuration": attack_update_request_data.configuration,
            "created_at": created_at_str,
            "updated_at": updated_at_str,
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 200  # OK for update
        mock_httpx_response.json.return_value = mock_updated_attack_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_attack = Attack.from_dict(mock_updated_attack_response_content)

        with patch(
            "hackagent.api.attack.attack_update.Attack.from_dict",
            return_value=mock_parsed_attack,
        ) as mock_from_dict:
            response = attack_update.sync_detailed(
                client=mock_client_instance,
                id=attack_id_to_update,
                body=attack_update_request_data,
            )

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.id, attack_id_to_update)
            self.assertEqual(response.parsed.type_, attack_update_request_data.type_)
            self.assertEqual(
                response.parsed.configuration, attack_update_request_data.configuration
            )
            self.assertEqual(
                response.parsed.updated_at,
                datetime.datetime.fromisoformat(updated_at_str.replace("Z", "+00:00")),
            )
            mock_from_dict.assert_called_once_with(mock_updated_attack_response_content)

            expected_kwargs = {
                "method": "put",
                "url": f"/api/attack/{attack_id_to_update}",
                "json": attack_update_request_data.to_dict(),
                "headers": {"Content-Type": "application/json"},
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.attack.attack_update.AuthenticatedClient")
    def test_attack_update_sync_detailed_error_not_found(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        attack_id_not_found = uuid.uuid4()
        attack_update_request_data = AttackRequest(
            type_="NON_EXISTENT_UPDATE", agent=uuid.uuid4(), configuration={}
        )

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 404
        mock_httpx_response.content = b"Attack Not Found For Update"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            attack_update.sync_detailed(
                client=mock_client_instance,
                id=attack_id_not_found,
                body=attack_update_request_data,
            )

        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.content, b"Attack Not Found For Update")

    @patch("hackagent.api.attack.attack_update.AuthenticatedClient")
    def test_attack_update_sync_detailed_error_raise_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        attack_id_error = uuid.uuid4()
        attack_update_request_data = AttackRequest(
            type_="UPDATE_ERROR_FALSE", agent=uuid.uuid4(), configuration={}
        )

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 400  # Bad Request for example
        mock_httpx_response.content = b"Invalid Attack Update Data"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = attack_update.sync_detailed(
            client=mock_client_instance,
            id=attack_id_error,
            body=attack_update_request_data,
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIsNone(response.parsed)


class TestAttackPartialUpdateAPI(unittest.TestCase):
    @patch("hackagent.api.attack.attack_partial_update.AuthenticatedClient")
    def test_attack_partial_update_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        attack_id_to_patch = uuid.uuid4()
        # Only updating configuration in this test case
        attack_patch_request_data = PatchedAttackRequest(
            configuration={"new_param": "new_value", "old_param": "updated_value"}
        )

        # Mock response should reflect the patched data along with existing data
        mock_agent_id_patch = uuid.uuid4()
        mock_org_id_patch = uuid.uuid4()
        created_at_str = "2023-05-01T10:00:00Z"
        updated_at_str = (
            "2023-05-01T13:00:00Z"  # Ensure updated_at reflects the patch time
        )

        mock_patched_attack_response_content = {
            "id": str(attack_id_to_patch),
            "type": "EXISTING_TYPE",  # Changed from type_ to type
            "agent": str(mock_agent_id_patch),  # Field not patched
            "agent_name": "Agent For Patched Attack",
            "owner": 5,
            "owner_username": "patcher_user",
            "organization": str(mock_org_id_patch),
            "organization_name": "Org For Patched Attack",
            "configuration": attack_patch_request_data.configuration,  # This is the patched field
            "created_at": created_at_str,
            "updated_at": updated_at_str,
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 200  # OK for partial update
        mock_httpx_response.json.return_value = mock_patched_attack_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_attack = Attack.from_dict(mock_patched_attack_response_content)

        with patch(
            "hackagent.api.attack.attack_partial_update.Attack.from_dict",
            return_value=mock_parsed_attack,
        ) as mock_from_dict:
            response = attack_partial_update.sync_detailed(
                client=mock_client_instance,
                id=attack_id_to_patch,
                body=attack_patch_request_data,
            )

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.id, attack_id_to_patch)
            # Check that unpatched fields (like type_) are present and unchanged from the mock server response
            self.assertEqual(
                response.parsed.type_, "EXISTING_TYPE"
            )  # Attribute access is still type_
            self.assertEqual(
                response.parsed.configuration, attack_patch_request_data.configuration
            )
            self.assertEqual(
                response.parsed.updated_at,
                datetime.datetime.fromisoformat(updated_at_str.replace("Z", "+00:00")),
            )
            mock_from_dict.assert_called_once_with(mock_patched_attack_response_content)

            expected_kwargs = {
                "method": "patch",
                "url": f"/api/attack/{attack_id_to_patch}",
                "json": attack_patch_request_data.to_dict(),
                "headers": {"Content-Type": "application/json"},
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.attack.attack_partial_update.AuthenticatedClient")
    def test_attack_partial_update_sync_detailed_error_not_found(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        attack_id_not_found = uuid.uuid4()
        attack_patch_request_data = PatchedAttackRequest(type_="NON_EXISTENT_PATCH")

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 404
        mock_httpx_response.content = b"Attack Not Found For Patch"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            attack_partial_update.sync_detailed(
                client=mock_client_instance,
                id=attack_id_not_found,
                body=attack_patch_request_data,
            )

        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.content, b"Attack Not Found For Patch")

    @patch("hackagent.api.attack.attack_partial_update.AuthenticatedClient")
    def test_attack_partial_update_sync_detailed_error_raise_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        attack_id_error = uuid.uuid4()
        attack_patch_request_data = PatchedAttackRequest(agent=uuid.uuid4())

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 400  # Bad Request
        mock_httpx_response.content = b"Invalid Attack Patch Data"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = attack_partial_update.sync_detailed(
            client=mock_client_instance,
            id=attack_id_error,
            body=attack_patch_request_data,
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIsNone(response.parsed)


class TestAttackDestroyAPI(unittest.TestCase):
    @patch("hackagent.api.attack.attack_destroy.AuthenticatedClient")
    def test_attack_destroy_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        attack_id_to_delete = uuid.uuid4()

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 204  # No Content for successful deletion
        mock_httpx_response.content = b""
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = attack_destroy.sync_detailed(
            client=mock_client_instance, id=attack_id_to_delete
        )

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        self.assertIsNone(response.parsed)  # No parsed content for 204

        expected_kwargs = {
            "method": "delete",
            "url": f"/api/attack/{attack_id_to_delete}",
        }
        mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.attack.attack_destroy.AuthenticatedClient")
    def test_attack_destroy_sync_detailed_error_not_found(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        attack_id_not_found = uuid.uuid4()

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 404
        mock_httpx_response.content = b"Attack Not Found For Deletion"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            attack_destroy.sync_detailed(
                client=mock_client_instance, id=attack_id_not_found
            )

        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.content, b"Attack Not Found For Deletion")

    @patch("hackagent.api.attack.attack_destroy.AuthenticatedClient")
    def test_attack_destroy_sync_detailed_error_raise_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        attack_id_error = uuid.uuid4()

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 500  # Internal Server Error
        mock_httpx_response.content = b"Deletion Failed Server Side - Attack"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = attack_destroy.sync_detailed(
            client=mock_client_instance, id=attack_id_error
        )

        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.assertIsNone(response.parsed)


if __name__ == "__main__":
    unittest.main()
