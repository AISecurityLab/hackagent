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
import uuid
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from dateutil.parser import isoparse

from hackagent import errors
from hackagent.api.key import key_create, key_destroy, key_list, key_retrieve
from hackagent.models.paginated_user_api_key_list import PaginatedUserAPIKeyList
from hackagent.models.user_api_key import UserAPIKey
from hackagent.models.user_api_key_request import UserAPIKeyRequest


class TestKeyListAPI(unittest.TestCase):
    @patch("hackagent.api.key.key_list.AuthenticatedClient")
    def test_key_list_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        mock_key_id = str(uuid.uuid4())  # This is the DB record ID
        mock_user_id = 123
        mock_org_id = uuid.uuid4()
        created_at_str = "2023-06-01T10:00:00Z"
        expiry_date_str = "2024-06-01T10:00:00Z"

        # Mock for UserProfileMinimal and OrganizationMinimal
        mock_user_detail_data = {
            "user": mock_user_id,
            "username": "key_user",
            "organization": str(mock_org_id),
        }
        mock_org_detail_data = {"id": str(mock_org_id), "name": "Key Org"}

        mock_api_key_data = {
            "id": mock_key_id,
            "name": "Test API Key",
            "prefix": "test_",
            "created": created_at_str,
            "revoked": False,
            "expiry_date": expiry_date_str,
            "user": mock_user_id,
            "user_detail": mock_user_detail_data,
            "organization": str(mock_org_id),
            "organization_detail": mock_org_detail_data,
            # 'key' field should NOT be present in list/retrieve responses
        }
        mock_response_content = {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [mock_api_key_data],
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 200
        mock_httpx_response.json.return_value = mock_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_object = PaginatedUserAPIKeyList.from_dict(mock_response_content)

        with patch(
            "hackagent.api.key.key_list.PaginatedUserAPIKeyList.from_dict",
            return_value=mock_parsed_object,
        ) as mock_from_dict:
            response = key_list.sync_detailed(client=mock_client_instance, page=1)

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.count, 1)
            self.assertTrue(
                isinstance(response.parsed.results, list)
                and len(response.parsed.results) > 0
            )

            retrieved_key = response.parsed.results[0]
            self.assertEqual(retrieved_key.id, mock_key_id)
            self.assertEqual(retrieved_key.name, "Test API Key")
            self.assertEqual(retrieved_key.prefix, "test_")
            self.assertFalse(retrieved_key.revoked)
            self.assertEqual(retrieved_key.user, mock_user_id)
            self.assertIsNotNone(retrieved_key.user_detail)
            self.assertEqual(retrieved_key.user_detail.username, "key_user")
            self.assertEqual(retrieved_key.user_detail.user, mock_user_id)
            self.assertEqual(retrieved_key.organization, mock_org_id)
            self.assertIsNotNone(retrieved_key.organization_detail)
            self.assertEqual(retrieved_key.organization_detail.name, "Key Org")
            self.assertEqual(retrieved_key.organization_detail.id, mock_org_id)

            self.assertEqual(retrieved_key.created, isoparse(created_at_str))

            if expiry_date_str and retrieved_key.expiry_date:
                self.assertEqual(retrieved_key.expiry_date, isoparse(expiry_date_str))

            mock_from_dict.assert_called_once_with(mock_response_content)

            expected_kwargs = {
                "method": "get",
                "url": "/key",
                "params": {"page": 1},
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.key.key_list.AuthenticatedClient")
    def test_key_list_sync_detailed_error_raise_on_unexpected_status_true(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 500
        mock_httpx_response.content = b"Server Error For Key List"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            key_list.sync_detailed(client=mock_client_instance)

        self.assertEqual(cm.exception.status_code, 500)
        self.assertEqual(cm.exception.content, b"Server Error For Key List")

    @patch("hackagent.api.key.key_list.AuthenticatedClient")
    def test_key_list_sync_detailed_error_raise_on_unexpected_status_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 403  # Forbidden
        mock_httpx_response.content = b"Forbidden Access to Key List"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = key_list.sync_detailed(client=mock_client_instance)

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIsNone(response.parsed)


class TestKeyCreateAPI(unittest.TestCase):
    @patch("hackagent.api.key.key_create.AuthenticatedClient")
    def test_key_create_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        key_request_data = UserAPIKeyRequest(name="My New Key")

        mock_created_key_id = str(uuid.uuid4())  # DB record ID
        mock_full_key_value = "test_thisIsTheFullKeyValueAbc123Xyz789"
        mock_prefix = "test_"
        mock_user_id_create = 456
        mock_org_id_create = uuid.uuid4()
        created_at_str = "2023-06-02T10:00:00Z"
        # Expiry date might be None or a date string upon creation
        expiry_date_create_str = None

        mock_user_detail_data_create = {
            "user": mock_user_id_create,
            "username": "key_creator",
            "organization": str(mock_org_id_create),
        }
        mock_org_detail_data_create = {
            "id": str(mock_org_id_create),
            "name": "Key Creator Org",
        }

        # Response upon creation includes the full 'key'
        mock_response_content = {
            "id": mock_created_key_id,
            "name": key_request_data.name,
            "prefix": mock_prefix,  # Server generates prefix
            "key": mock_full_key_value,  # Server generates full key
            "created": created_at_str,
            "revoked": False,
            "expiry_date": expiry_date_create_str,
            "user": mock_user_id_create,
            "user_detail": mock_user_detail_data_create,
            "organization": str(mock_org_id_create),
            "organization_detail": mock_org_detail_data_create,
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 201  # Created
        mock_httpx_response.json.return_value = mock_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        # For UserAPIKey.from_dict to work, it needs the 'key' field if present in src_dict.
        # The UserAPIKey model itself doesn't list 'key' as a direct attribute in its __init__,
        # but from_dict might handle it if it's in the source dictionary.
        # Let's ensure our UserAPIKey model definition can handle this or adjust mock.
        # From UserAPIKey model: "The full key is only shown once upon creation by the ViewSet."
        # This implies the model should be able to parse it if present.

        # We also need to add 'key' to the UserAPIKey model for from_dict to parse it correctly if it is there.
        # However, the provided UserAPIKey model doesn't have 'key' as an attribute.
        # This is a potential inconsistency. For now, we assume UserAPIKey.from_dict
        # will correctly parse it if it's in the dict, and it becomes an additional_property.
        # Alternatively, the server might return a different model for creation that includes the key.
        # Given the current models, the 'key' will likely go into additional_properties.

        mock_parsed_key = UserAPIKey.from_dict(mock_response_content)

        with patch(
            "hackagent.api.key.key_create.UserAPIKey.from_dict",
            return_value=mock_parsed_key,
        ) as mock_from_dict:
            response = key_create.sync_detailed(
                client=mock_client_instance, body=key_request_data
            )

            self.assertEqual(response.status_code, HTTPStatus.CREATED)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.id, mock_created_key_id)
            self.assertEqual(response.parsed.name, key_request_data.name)
            self.assertEqual(response.parsed.prefix, mock_prefix)

            # Assert that the full key is part of the parsed object, likely via additional_properties
            # if UserAPIKey model doesn't explicitly define it.
            # We need to check how UserAPIKey is defined or how from_dict handles extra fields.
            # Based on UserAPIKey.from_dict, it should store extra fields in additional_properties
            self.assertIn("key", response.parsed.additional_properties)
            self.assertEqual(
                response.parsed.additional_properties["key"], mock_full_key_value
            )

            # Assertions for user_detail and organization_detail
            # Assuming user_detail and organization_detail are parsed into objects now
            self.assertIsNotNone(response.parsed.user_detail)
            self.assertEqual(response.parsed.user_detail.username, "key_creator")
            self.assertEqual(response.parsed.user_detail.user, mock_user_id_create)
            self.assertIsNotNone(response.parsed.organization_detail)
            self.assertEqual(
                response.parsed.organization_detail.name, "Key Creator Org"
            )
            self.assertEqual(response.parsed.organization_detail.id, mock_org_id_create)

            mock_from_dict.assert_called_once_with(mock_response_content)

            expected_kwargs = {
                "method": "post",
                "url": "/key",
                "json": key_request_data.to_dict(),
                "headers": {"Content-Type": "application/json"},
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.key.key_create.AuthenticatedClient")
    def test_key_create_sync_detailed_error_raise_on_unexpected_status_true(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        key_request_data = UserAPIKeyRequest(name="Error Key Name")

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 400
        mock_httpx_response.content = b"Bad Key Request Data"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            key_create.sync_detailed(client=mock_client_instance, body=key_request_data)

        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(cm.exception.content, b"Bad Key Request Data")

    @patch("hackagent.api.key.key_create.AuthenticatedClient")
    def test_key_create_sync_detailed_error_raise_on_unexpected_status_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        key_request_data = UserAPIKeyRequest(name="Error Key False Name")

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 401
        mock_httpx_response.content = b"Unauthorized Key Creation"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = key_create.sync_detailed(
            client=mock_client_instance, body=key_request_data
        )

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
        self.assertIsNone(response.parsed)


class TestKeyRetrieveAPI(unittest.TestCase):
    @patch("hackagent.api.key.key_retrieve.AuthenticatedClient")
    def test_key_retrieve_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        key_prefix_to_retrieve = "retr_"
        mock_retrieved_key_id = str(uuid.uuid4())
        mock_user_id_retrieve = 789
        mock_org_id_retrieve = uuid.uuid4()
        created_at_retrieve_str = "2023-06-03T10:00:00Z"
        expiry_date_retrieve_str = None  # Example: Key with no expiry

        mock_user_detail_data_retrieve = {
            "user": mock_user_id_retrieve,
            "username": "key_retriever",
            "organization": str(mock_org_id_retrieve),
        }
        mock_org_detail_data_retrieve = {
            "id": str(mock_org_id_retrieve),
            "name": "Key Retriever Org",
        }

        mock_response_content = {
            "id": mock_retrieved_key_id,
            "name": "Retrieved Key Name",
            "prefix": key_prefix_to_retrieve,
            # "key": should NOT be present here
            "created": created_at_retrieve_str,
            "revoked": True,  # Example: a revoked key
            "expiry_date": expiry_date_retrieve_str,
            "user": mock_user_id_retrieve,
            "user_detail": mock_user_detail_data_retrieve,
            "organization": str(mock_org_id_retrieve),
            "organization_detail": mock_org_detail_data_retrieve,
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 200
        mock_httpx_response.json.return_value = mock_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_key = UserAPIKey.from_dict(mock_response_content)

        with patch(
            "hackagent.api.key.key_retrieve.UserAPIKey.from_dict",
            return_value=mock_parsed_key,
        ) as mock_from_dict:
            response = key_retrieve.sync_detailed(
                client=mock_client_instance, prefix=key_prefix_to_retrieve
            )

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.id, mock_retrieved_key_id)
            self.assertEqual(response.parsed.name, "Retrieved Key Name")
            self.assertEqual(response.parsed.prefix, key_prefix_to_retrieve)
            self.assertTrue(response.parsed.revoked)
            self.assertNotIn(
                "key", response.parsed.additional_properties
            )  # Ensure full key is not present

            # Assertions for user_detail and organization_detail
            self.assertIsNotNone(response.parsed.user_detail)
            self.assertEqual(response.parsed.user_detail.username, "key_retriever")
            self.assertEqual(response.parsed.user_detail.user, mock_user_id_retrieve)
            self.assertIsNotNone(response.parsed.organization_detail)
            self.assertEqual(
                response.parsed.organization_detail.name, "Key Retriever Org"
            )
            self.assertEqual(
                response.parsed.organization_detail.id, mock_org_id_retrieve
            )

            mock_from_dict.assert_called_once_with(mock_response_content)

            expected_kwargs = {
                "method": "get",
                "url": f"/key/{key_prefix_to_retrieve}",
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.key.key_retrieve.AuthenticatedClient")
    def test_key_retrieve_sync_detailed_error_not_found(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        key_prefix_not_found = "nonexist_"
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 404
        mock_httpx_response.content = b"API Key Not Found"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            key_retrieve.sync_detailed(
                client=mock_client_instance, prefix=key_prefix_not_found
            )

        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.content, b"API Key Not Found")

    @patch("hackagent.api.key.key_retrieve.AuthenticatedClient")
    def test_key_retrieve_sync_detailed_error_raise_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        key_prefix_error = "error_"
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 500
        mock_httpx_response.content = b"Server Side Issue For Key Retrieve"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = key_retrieve.sync_detailed(
            client=mock_client_instance, prefix=key_prefix_error
        )

        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.assertIsNone(response.parsed)


class TestKeyDestroyAPI(unittest.TestCase):
    @patch("hackagent.api.key.key_destroy.AuthenticatedClient")
    def test_key_destroy_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        key_prefix_to_delete = "delme_"

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 204  # No Content for successful deletion
        mock_httpx_response.content = b""
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = key_destroy.sync_detailed(
            client=mock_client_instance, prefix=key_prefix_to_delete
        )

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        self.assertIsNone(response.parsed)  # No parsed content for 204

        expected_kwargs = {
            "method": "delete",
            "url": f"/key/{key_prefix_to_delete}",
        }
        mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.key.key_destroy.AuthenticatedClient")
    def test_key_destroy_sync_detailed_error_not_found(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        key_prefix_not_found = "defnotexist_"

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 404
        mock_httpx_response.content = b"API Key Not Found For Deletion"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            key_destroy.sync_detailed(
                client=mock_client_instance, prefix=key_prefix_not_found
            )

        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.content, b"API Key Not Found For Deletion")

    @patch("hackagent.api.key.key_destroy.AuthenticatedClient")
    def test_key_destroy_sync_detailed_error_raise_false(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        key_prefix_error_delete = "errdel_"

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 500  # Internal Server Error
        mock_httpx_response.content = b"Deletion Failed Server Side - Key"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = key_destroy.sync_detailed(
            client=mock_client_instance, prefix=key_prefix_error_delete
        )

        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.assertIsNone(response.parsed)


if __name__ == "__main__":
    unittest.main()
