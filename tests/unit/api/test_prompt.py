# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


import unittest
import uuid
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from dateutil.parser import isoparse

from hackagent import errors
from hackagent.api.prompt import (
    prompt_create,
    prompt_destroy,
    prompt_list,
    prompt_partial_update,
    prompt_retrieve,
    prompt_update,
)
from hackagent.api.models import PaginatedPromptList
from hackagent.api.models import PatchedPromptRequest
from hackagent.api.models import Prompt
from hackagent.api.models import PromptRequest


class TestPromptListAPI(unittest.TestCase):
    @patch("hackagent.api.prompt.prompt_list.AuthenticatedClient")
    def test_prompt_list_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        mock_prompt_id = uuid.uuid4()
        mock_org_id = uuid.uuid4()
        mock_owner_id = 123  # Assuming owner is an int ID if present
        created_at_str = "2023-07-01T10:00:00Z"
        updated_at_str = "2023-07-01T11:00:00Z"

        mock_org_detail_data = {"id": str(mock_org_id), "name": "Prompt Org"}
        # Owner detail can be None or UserProfileMinimal
        mock_owner_detail_data = {
            "user": mock_owner_id,
            "username": "prompt_owner",
            "organization": str(mock_org_id),
        }

        mock_prompt_data = {
            "id": str(mock_prompt_id),
            "name": "Test Prompt",
            "prompt_text": "This is a test prompt text.",
            "organization": str(mock_org_id),
            "organization_detail": mock_org_detail_data,
            "owner_detail": mock_owner_detail_data,  # Can also be None
            "created_at": created_at_str,
            "updated_at": updated_at_str,
            "category": "TestCategory",
            "tags": ["test", "api"],
            "evaluation_criteria": "Ensure it is a test.",
            "owner": mock_owner_id,  # Can also be None or UNSET
            # "expected_tool_calls": UNSET,
            # "expected_output_pattern": UNSET,
            # "reference_output": UNSET
        }
        mock_response_content = {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [mock_prompt_data],
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 200
        mock_httpx_response.json.return_value = mock_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        # Create a PaginatedPromptList instance from the mock content
        mock_parsed_object = PaginatedPromptList.model_validate(mock_response_content)

        with patch(
            "hackagent.api.prompt.prompt_list.PaginatedPromptList.model_validate",
            return_value=mock_parsed_object,
        ) as mock_model_validate:
            response = prompt_list.sync_detailed(
                client=mock_client_instance, category="TestCategory", page=1
            )

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.count, 1)
            self.assertTrue(
                isinstance(response.parsed.results, list)
                and len(response.parsed.results) > 0
            )

            retrieved_prompt = response.parsed.results[0]
            self.assertEqual(retrieved_prompt.id, mock_prompt_id)
            self.assertEqual(retrieved_prompt.name, "Test Prompt")
            self.assertEqual(
                retrieved_prompt.prompt_text, "This is a test prompt text."
            )
            self.assertEqual(retrieved_prompt.organization, mock_org_id)
            self.assertIsNotNone(retrieved_prompt.organization_detail)
            self.assertEqual(retrieved_prompt.organization_detail.name, "Prompt Org")
            self.assertEqual(retrieved_prompt.organization_detail.id, mock_org_id)

            self.assertIsNotNone(retrieved_prompt.owner_detail)
            if (
                retrieved_prompt.owner_detail
            ):  # Check to satisfy type checker and handle possible None
                self.assertEqual(retrieved_prompt.owner_detail.username, "prompt_owner")
                self.assertEqual(retrieved_prompt.owner_detail.user, mock_owner_id)
                self.assertEqual(
                    retrieved_prompt.owner_detail.organization, mock_org_id
                )

            self.assertEqual(retrieved_prompt.created_at, isoparse(created_at_str))
            self.assertEqual(retrieved_prompt.updated_at, isoparse(updated_at_str))
            self.assertEqual(retrieved_prompt.category, "TestCategory")
            self.assertEqual(retrieved_prompt.tags, ["test", "api"])
            self.assertEqual(
                retrieved_prompt.evaluation_criteria, "Ensure it is a test."
            )
            self.assertEqual(retrieved_prompt.owner, mock_owner_id)

            mock_model_validate.assert_called_once_with(mock_response_content)

            expected_kwargs = {
                "method": "get",
                "url": "/prompt",
                "params": {"category": "TestCategory", "page": 1},
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.prompt.prompt_list.AuthenticatedClient")
    def test_prompt_list_sync_detailed_error_raise_on_unexpected_status_true(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 500
        mock_httpx_response.content = b"Server Error For Prompt List"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            prompt_list.sync_detailed(client=mock_client_instance)

        self.assertEqual(cm.exception.status_code, 500)
        self.assertEqual(cm.exception.content, b"Server Error For Prompt List")

    @patch("hackagent.api.prompt.prompt_list.AuthenticatedClient")
    def test_prompt_list_sync_detailed_error_raise_on_unexpected_status_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 403  # Forbidden
        mock_httpx_response.content = b"Forbidden Access to Prompt List"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = prompt_list.sync_detailed(client=mock_client_instance)

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIsNone(response.parsed)


class TestPromptCreateAPI(unittest.TestCase):
    @patch("hackagent.api.prompt.prompt_create.AuthenticatedClient")
    def test_prompt_create_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        # These two variables are unused
        # mock_org_detail_data_create = {"id": str(mock_org_id_create), "name": "Prompt Creator Org"}
        # mock_owner_detail_data_create = {"id": mock_owner_id_create, "username": "prompt_creator_user"}

        prompt_request_data = PromptRequest(
            name="New Test Prompt",
            prompt_text="This is the text for the new prompt.",
            category="CreationTest",
            tags=["new", "create"],
            evaluation_criteria="Successfully created.",
        )

        mock_created_prompt_id = uuid.uuid4()
        mock_org_id_create_resp = uuid.uuid4()  # For the response
        mock_owner_id_create_resp = 101  # For the response
        created_at_create_str = "2023-07-02T10:00:00Z"
        updated_at_create_str = (
            "2023-07-02T10:00:00Z"  # Typically same as created_at upon creation
        )

        # Use the _resp IDs for the mock_response_content details
        mock_response_org_detail = {
            "id": str(mock_org_id_create_resp),
            "name": "Prompt Creator Org",
        }
        mock_response_owner_detail = {
            "user": mock_owner_id_create_resp,
            "username": "prompt_creator_user",
            "organization": str(mock_org_id_create_resp),
        }

        mock_response_content = {
            "id": str(mock_created_prompt_id),
            "name": prompt_request_data.name,
            "prompt_text": prompt_request_data.prompt_text,
            "organization": str(mock_org_id_create_resp),  # Organization from response
            "organization_detail": mock_response_org_detail,  # Use resp detail
            "owner_detail": mock_response_owner_detail,  # Use resp detail
            "created_at": created_at_create_str,
            "updated_at": updated_at_create_str,
            "category": prompt_request_data.category,
            "tags": prompt_request_data.tags,
            "evaluation_criteria": prompt_request_data.evaluation_criteria,
            "owner": mock_owner_id_create_resp,
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 201  # Created
        mock_httpx_response.json.return_value = mock_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_prompt = Prompt.model_validate(mock_response_content)

        with patch(
            "hackagent.api.prompt.prompt_create.Prompt.model_validate",
            return_value=mock_parsed_prompt,
        ) as mock_model_validate:
            response = prompt_create.sync_detailed(
                client=mock_client_instance, body=prompt_request_data
            )

            self.assertEqual(response.status_code, HTTPStatus.CREATED)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.id, mock_created_prompt_id)
            self.assertEqual(response.parsed.name, prompt_request_data.name)
            self.assertEqual(
                response.parsed.prompt_text, prompt_request_data.prompt_text
            )
            # PromptRequest doesn't have organization field - it's set by the backend
            self.assertEqual(response.parsed.organization, mock_org_id_create_resp)
            self.assertEqual(response.parsed.category, prompt_request_data.category)
            self.assertEqual(response.parsed.tags, prompt_request_data.tags)
            self.assertEqual(
                response.parsed.evaluation_criteria,
                prompt_request_data.evaluation_criteria,
            )

            self.assertIsNotNone(response.parsed.organization_detail)
            self.assertEqual(
                response.parsed.organization_detail.name, "Prompt Creator Org"
            )
            self.assertEqual(
                response.parsed.organization_detail.id, mock_org_id_create_resp
            )

            self.assertIsNotNone(response.parsed.owner_detail)
            if response.parsed.owner_detail:  # Owner can be None
                self.assertEqual(
                    response.parsed.owner_detail.username, "prompt_creator_user"
                )
                self.assertEqual(
                    response.parsed.owner_detail.user, mock_owner_id_create_resp
                )

            self.assertEqual(
                response.parsed.created_at, isoparse(created_at_create_str)
            )
            self.assertEqual(
                response.parsed.updated_at, isoparse(updated_at_create_str)
            )

            mock_model_validate.assert_called_once_with(mock_response_content)

            expected_kwargs = {
                "method": "post",
                "url": "/prompt",
                "json": prompt_request_data.model_dump(by_alias=True, mode="json", exclude_none=True),
                "headers": {"Content-Type": "application/json"},
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.prompt.prompt_create.AuthenticatedClient")
    def test_prompt_create_sync_detailed_error_raise_on_unexpected_status_true(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        prompt_request_data = PromptRequest(name="Error Prompt", prompt_text="text")

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 400
        mock_httpx_response.content = b"Bad Prompt Request Data"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            prompt_create.sync_detailed(
                client=mock_client_instance, body=prompt_request_data
            )

        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(cm.exception.content, b"Bad Prompt Request Data")

    @patch("hackagent.api.prompt.prompt_create.AuthenticatedClient")
    def test_prompt_create_sync_detailed_error_raise_on_unexpected_status_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        prompt_request_data = PromptRequest(
            name="Error False Prompt", prompt_text="text"
        )

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 401
        mock_httpx_response.content = b"Unauthorized Prompt Creation"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = prompt_create.sync_detailed(
            client=mock_client_instance, body=prompt_request_data
        )

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
        self.assertIsNone(response.parsed)


class TestPromptRetrieveAPI(unittest.TestCase):
    @patch("hackagent.api.prompt.prompt_retrieve.AuthenticatedClient")
    def test_prompt_retrieve_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        prompt_id_to_retrieve = uuid.uuid4()
        mock_org_id_retrieve = uuid.uuid4()
        mock_owner_id_retrieve = 102  # Example ID
        created_at_retrieve_str = "2023-07-03T10:00:00Z"
        updated_at_retrieve_str = "2023-07-03T11:00:00Z"

        mock_org_detail_data_retrieve = {
            "id": str(mock_org_id_retrieve),
            "name": "Retrieved Prompt Org",
        }
        mock_owner_detail_data_retrieve = {
            "user": mock_owner_id_retrieve,
            "username": "prompt_retriever_user",
            "organization": str(mock_org_id_retrieve),
        }

        mock_response_content = {
            "id": str(prompt_id_to_retrieve),
            "name": "Retrieved Prompt Name",
            "prompt_text": "Retrieved prompt text.",  # Reverted prompt_text
            "organization": str(mock_org_id_retrieve),
            "organization_detail": mock_org_detail_data_retrieve,
            "owner": mock_owner_id_retrieve,
            "owner_detail": mock_owner_detail_data_retrieve,
            "category": "RetrievalTest",
            "created_at": created_at_retrieve_str,
            "updated_at": updated_at_retrieve_str,
            "tags": ["retrieved"],
            "evaluation_criteria": "Successfully retrieved.",
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 200
        mock_httpx_response.json.return_value = mock_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_prompt = Prompt.model_validate(mock_response_content)

        with patch(
            "hackagent.api.prompt.prompt_retrieve.Prompt.model_validate",
            return_value=mock_parsed_prompt,
        ) as mock_model_validate:
            response = prompt_retrieve.sync_detailed(
                client=mock_client_instance, id=prompt_id_to_retrieve
            )

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.id, prompt_id_to_retrieve)
            self.assertEqual(response.parsed.name, "Retrieved Prompt Name")
            self.assertEqual(response.parsed.prompt_text, "Retrieved prompt text.")
            self.assertIsNotNone(response.parsed.organization_detail)
            self.assertEqual(
                response.parsed.organization_detail.name, "Retrieved Prompt Org"
            )
            self.assertEqual(
                response.parsed.organization_detail.id, mock_org_id_retrieve
            )

            self.assertIsNotNone(response.parsed.owner_detail)
            if response.parsed.owner_detail:
                self.assertEqual(
                    response.parsed.owner_detail.username, "prompt_retriever_user"
                )
                self.assertEqual(
                    response.parsed.owner_detail.user, mock_owner_id_retrieve
                )
            self.assertEqual(response.parsed.category, "RetrievalTest")

            self.assertEqual(
                response.parsed.owner_detail.organization, mock_org_id_retrieve
            )  # ensure this is UUID

            # Check timestamps
            self.assertEqual(
                response.parsed.created_at, isoparse(created_at_retrieve_str)
            )
            self.assertEqual(
                response.parsed.updated_at, isoparse(updated_at_retrieve_str)
            )

            mock_model_validate.assert_called_once_with(mock_response_content)

            expected_kwargs = {
                "method": "get",
                "url": f"/prompt/{prompt_id_to_retrieve}",
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.prompt.prompt_retrieve.AuthenticatedClient")
    def test_prompt_retrieve_sync_detailed_error_not_found(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        prompt_id_not_found = uuid.uuid4()
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 404
        mock_httpx_response.content = b"Prompt Not Found"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            prompt_retrieve.sync_detailed(
                client=mock_client_instance, id=prompt_id_not_found
            )

        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.content, b"Prompt Not Found")

    @patch("hackagent.api.prompt.prompt_retrieve.AuthenticatedClient")
    def test_prompt_retrieve_sync_detailed_error_raise_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        prompt_id_error = uuid.uuid4()
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 500
        mock_httpx_response.content = b"Server Side Issue For Prompt Retrieve"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = prompt_retrieve.sync_detailed(
            client=mock_client_instance, id=prompt_id_error
        )

        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.assertIsNone(response.parsed)


class TestPromptUpdateAPI(unittest.TestCase):
    @patch("hackagent.api.prompt.prompt_update.AuthenticatedClient")
    def test_prompt_update_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        prompt_id_to_update = uuid.uuid4()
        mock_org_id_update = uuid.uuid4()  # Org ID for the request body

        prompt_update_request_data = PromptRequest(
            name="Updated Test Prompt",
            prompt_text="This is the updated text for the prompt.",
            category="UpdateTest",
            tags=["updated", "put"],
            evaluation_criteria="Successfully updated.",
        )

        # Mock response content might reflect the update and new updated_at time
        mock_owner_id_update_resp = 1011
        updated_at_update_str = "2023-07-04T12:00:00Z"
        # Assume created_at remains the same, organization_detail and owner_detail fetched by server
        mock_org_detail_data_update_resp = {
            "id": str(mock_org_id_update),
            "name": "Updated Prompt Org",
        }
        mock_owner_detail_data_update_resp = {
            "user": mock_owner_id_update_resp,
            "username": "updater_user_prompt",
            "organization": str(mock_org_id_update),
        }
        # Assume created_at is not changed by update; it will be part of the response from server for the existing object
        original_created_at_str = "2023-07-04T10:00:00Z"

        mock_updated_prompt_response_content = {
            "id": str(prompt_id_to_update),
            "name": prompt_update_request_data.name,
            "prompt_text": prompt_update_request_data.prompt_text,
            "organization": str(mock_org_id_update),  # Organization from response
            "organization_detail": mock_org_detail_data_update_resp,
            "owner_detail": mock_owner_detail_data_update_resp,
            "created_at": original_created_at_str,  # Should be original creation time
            "updated_at": updated_at_update_str,  # Should reflect the update
            "category": prompt_update_request_data.category,
            "tags": prompt_update_request_data.tags,
            "evaluation_criteria": prompt_update_request_data.evaluation_criteria,
            "owner": mock_owner_id_update_resp,
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 200  # OK for successful update
        mock_httpx_response.json.return_value = mock_updated_prompt_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_prompt = Prompt.model_validate(mock_updated_prompt_response_content)

        with patch(
            "hackagent.api.prompt.prompt_update.Prompt.model_validate",
            return_value=mock_parsed_prompt,
        ) as mock_model_validate:
            response = prompt_update.sync_detailed(
                client=mock_client_instance,
                id=prompt_id_to_update,
                body=prompt_update_request_data,
            )

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.id, prompt_id_to_update)
            self.assertEqual(response.parsed.name, prompt_update_request_data.name)
            self.assertEqual(
                response.parsed.prompt_text, prompt_update_request_data.prompt_text
            )
            self.assertIsNotNone(response.parsed.organization_detail)
            self.assertEqual(
                response.parsed.organization_detail.name, "Updated Prompt Org"
            )
            self.assertEqual(response.parsed.organization_detail.id, mock_org_id_update)

            self.assertIsNotNone(response.parsed.owner_detail)
            if response.parsed.owner_detail:  # Owner might not be updated or present
                self.assertEqual(
                    response.parsed.owner_detail.username, "updater_user_prompt"
                )
                self.assertEqual(
                    response.parsed.owner_detail.user, mock_owner_id_update_resp
                )

            # Timestamp of original creation should ideally remain, updated_at should change
            self.assertEqual(
                response.parsed.created_at, isoparse(original_created_at_str)
            )
            self.assertEqual(
                response.parsed.updated_at, isoparse(updated_at_update_str)
            )

            self.assertEqual(
                response.parsed.owner_detail.organization, mock_org_id_update
            )

            # Check timestamps (updated_at should change, created_at should not)
            self.assertEqual(
                response.parsed.created_at, isoparse(original_created_at_str)
            )  # Assuming created_at isn't changed by PUT
            self.assertEqual(
                response.parsed.updated_at, isoparse(updated_at_update_str)
            )

            mock_model_validate.assert_called_once_with(mock_updated_prompt_response_content)

            expected_kwargs = {
                "method": "put",
                "url": f"/prompt/{prompt_id_to_update}",
                "json": prompt_update_request_data.model_dump(by_alias=True, mode="json", exclude_none=True),
                "headers": {"Content-Type": "application/json"},
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.prompt.prompt_update.AuthenticatedClient")
    def test_prompt_update_sync_detailed_error_not_found(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        prompt_id_not_found = uuid.uuid4()
        update_data = PromptRequest(name="Upd", prompt_text="t")  # Dummy data

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 404
        mock_httpx_response.content = b"Prompt Not Found For Update"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            prompt_update.sync_detailed(
                client=mock_client_instance, id=prompt_id_not_found, body=update_data
            )

        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.content, b"Prompt Not Found For Update")

    @patch("hackagent.api.prompt.prompt_update.AuthenticatedClient")
    def test_prompt_update_sync_detailed_error_raise_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        prompt_id_error_update = uuid.uuid4()
        update_data_error = PromptRequest(name="UpdErr", prompt_text="te")  # Dummy data

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 400  # Bad Request (e.g. validation error)
        mock_httpx_response.content = b"Update Failed Validation - Prompt"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = prompt_update.sync_detailed(
            client=mock_client_instance,
            id=prompt_id_error_update,
            body=update_data_error,
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIsNone(response.parsed)


class TestPromptPartialUpdateAPI(unittest.TestCase):
    @patch("hackagent.api.prompt.prompt_partial_update.AuthenticatedClient")
    def test_prompt_partial_update_sync_detailed_success_patch_name_category(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        prompt_id_to_patch = uuid.uuid4()

        # Only updating name and category
        prompt_patch_request_data = PatchedPromptRequest(
            name="Patched Prompt Name",
            category="PatchTestCategory",
            # prompt_text, organization, tags, etc., are UNSET and won't be sent
        )

        # Mock response should show the patched fields and existing values for others
        mock_org_id_patch_resp = uuid.uuid4()
        mock_owner_id_patch_resp = 1213
        original_created_at_patch_str = "2023-07-05T09:00:00Z"
        updated_at_patch_str = "2023-07-05T14:00:00Z"
        original_prompt_text = "Original prompt text before patch."

        mock_org_detail_data_patch_resp = {
            "id": str(mock_org_id_patch_resp),
            "name": "Prompt Patcher Org",
        }
        mock_owner_detail_data_patch_resp = {
            "user": mock_owner_id_patch_resp,
            "username": "prompt_patcher_user",
            "organization": str(mock_org_id_patch_resp),
        }

        mock_patched_prompt_response_content = {
            "id": str(prompt_id_to_patch),
            "name": prompt_patch_request_data.name,  # Patched
            "prompt_text": original_prompt_text,  # Should be original
            "organization": str(mock_org_id_patch_resp),  # Should be original/current
            "organization_detail": mock_org_detail_data_patch_resp,
            "owner_detail": mock_owner_detail_data_patch_resp,
            "created_at": original_created_at_patch_str,
            "updated_at": updated_at_patch_str,  # Should reflect the patch time
            "category": prompt_patch_request_data.category,  # Patched
            "tags": ["original_tag"],  # Should be original/current
            "evaluation_criteria": "Original criteria.",  # Should be original/current
            "owner": mock_owner_id_patch_resp,
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 200  # OK for successful patch
        mock_httpx_response.json.return_value = mock_patched_prompt_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_prompt = Prompt.model_validate(mock_patched_prompt_response_content)

        with patch(
            "hackagent.api.prompt.prompt_partial_update.Prompt.model_validate",
            return_value=mock_parsed_prompt,
        ) as mock_model_validate:
            response = prompt_partial_update.sync_detailed(
                client=mock_client_instance,
                id=prompt_id_to_patch,
                body=prompt_patch_request_data,
            )

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.id, prompt_id_to_patch)
            self.assertEqual(response.parsed.name, prompt_patch_request_data.name)
            self.assertEqual(
                response.parsed.category, prompt_patch_request_data.category
            )
            self.assertEqual(
                response.parsed.prompt_text, original_prompt_text
            )  # Verify unpatched field
            self.assertEqual(response.parsed.updated_at, isoparse(updated_at_patch_str))

            self.assertEqual(
                response.parsed.owner_detail.organization, mock_org_id_patch_resp
            )

            # Check timestamps (updated_at should change)
            # created_at should remain from the original mock_prompt_data_partial_update
            self.assertEqual(
                response.parsed.created_at, isoparse(original_created_at_patch_str)
            )
            self.assertEqual(response.parsed.updated_at, isoparse(updated_at_patch_str))

            mock_model_validate.assert_called_once_with(mock_patched_prompt_response_content)

            expected_kwargs = {
                "method": "patch",
                "url": f"/prompt/{prompt_id_to_patch}",
                "json": prompt_patch_request_data.model_dump(by_alias=True, mode="json", exclude_none=True),  # Only name and category should be in dict
                "headers": {"Content-Type": "application/json"},
            }
            # Verify that to_dict() only contains the fields we set
            request_dict = prompt_patch_request_data.model_dump(by_alias=True, mode="json", exclude_none=True)
            self.assertIn("name", request_dict)
            self.assertIn("category", request_dict)
            self.assertIsNone(request_dict.get("prompt_text"))  # Unset optional fields serialize as None
            self.assertIsNone(request_dict.get("organization"))  # Unset optional fields serialize as None

            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.prompt.prompt_partial_update.AuthenticatedClient")
    def test_prompt_partial_update_sync_detailed_error_not_found(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        prompt_id_not_found = uuid.uuid4()
        patch_data = PatchedPromptRequest(name="PatchFail")

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 404
        mock_httpx_response.content = b"Prompt Not Found For Patch"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            prompt_partial_update.sync_detailed(
                client=mock_client_instance, id=prompt_id_not_found, body=patch_data
            )

        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.content, b"Prompt Not Found For Patch")

    @patch("hackagent.api.prompt.prompt_partial_update.AuthenticatedClient")
    def test_prompt_partial_update_sync_detailed_error_raise_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        prompt_id_error_patch = uuid.uuid4()
        patch_data_error = PatchedPromptRequest(prompt_text="New Text Error")

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 400  # Bad Request
        mock_httpx_response.content = b"Patch Failed Validation - Prompt"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = prompt_partial_update.sync_detailed(
            client=mock_client_instance, id=prompt_id_error_patch, body=patch_data_error
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIsNone(response.parsed)


class TestPromptDestroyAPI(unittest.TestCase):
    @patch("hackagent.api.prompt.prompt_destroy.AuthenticatedClient")
    def test_prompt_destroy_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        prompt_id_to_delete = uuid.uuid4()

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 204  # No Content for successful deletion
        mock_httpx_response.content = b""
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = prompt_destroy.sync_detailed(
            client=mock_client_instance, id=prompt_id_to_delete
        )

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        self.assertIsNone(response.parsed)  # No parsed content for 204

        expected_kwargs = {
            "method": "delete",
            "url": f"/prompt/{prompt_id_to_delete}",
        }
        mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.prompt.prompt_destroy.AuthenticatedClient")
    def test_prompt_destroy_sync_detailed_error_not_found(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        prompt_id_not_found_delete = uuid.uuid4()

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 404
        mock_httpx_response.content = b"Prompt Not Found For Deletion"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            prompt_destroy.sync_detailed(
                client=mock_client_instance, id=prompt_id_not_found_delete
            )

        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.content, b"Prompt Not Found For Deletion")

    @patch("hackagent.api.prompt.prompt_destroy.AuthenticatedClient")
    def test_prompt_destroy_sync_detailed_error_raise_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        prompt_id_error_delete = uuid.uuid4()

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 500  # Internal Server Error
        mock_httpx_response.content = b"Deletion Failed Server Side - Prompt"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = prompt_destroy.sync_detailed(
            client=mock_client_instance, id=prompt_id_error_delete
        )

        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.assertIsNone(response.parsed)


if __name__ == """__main__""":
    unittest.main()
