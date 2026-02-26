# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


import unittest
import uuid
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from dateutil.parser import isoparse

from hackagent import errors
from hackagent.api.run import (
    run_create,
    run_destroy,
    run_list,
    run_partial_update,
    run_result_create,
    run_retrieve,
    run_run_tests_create,
    run_update,
)  # Added run_run_tests_create
from hackagent.api.models import (
    EvaluationStatusEnum,
)  # For nested Result.evaluation_status
from hackagent.api.models import PaginatedRunList
from hackagent.api.models import PatchedRunRequest  # Added
from hackagent.api.models import Result  # For nested results within a Run
from hackagent.api.models import (
    ResultRequest as RunResultCreateRequest,
)  # Alias to avoid confusion with main ResultRequest
from hackagent.api.models import Run
from hackagent.api.models import StatusEnum  # For run_list filter
from hackagent.api.models import RunRequest  # Added
from hackagent.api.models import StatusEnum  # For Run status field
from hackagent.types import UNSET


class TestRunListAPI(unittest.TestCase):
    @patch("hackagent.api.run.run_list.AuthenticatedClient")
    def test_run_list_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        mock_run_id = uuid.uuid4()
        mock_agent_id = uuid.uuid4()
        mock_org_id = uuid.uuid4()
        mock_attack_id = uuid.uuid4()
        timestamp_str = "2023-09-01T10:00:00Z"

        # Mock for a Result within the Run's results list
        mock_result_id_in_run = uuid.uuid4()
        mock_trace_data_in_result = {
            "id": 1,
            "result": str(mock_result_id_in_run),
            "sequence": 1,
            "type": "MESSAGE",
            "content": "Nested trace",
            "timestamp": timestamp_str,
            "metadata": {},
        }
        mock_result_data_in_run = {
            "id": str(mock_result_id_in_run),
            "run": str(mock_run_id),
            "run_id": str(mock_run_id),
            "prompt_name": "Prompt in Run's Result",
            "timestamp": timestamp_str,
            "traces": [mock_trace_data_in_result],
            "prompt": str(uuid.uuid4()),
            "evaluation_status": EvaluationStatusEnum.NOT_EVALUATED.value,
            "response_body": "Response in Run's Result",
        }

        mock_run_data = {
            "id": str(mock_run_id),
            "agent": str(mock_agent_id),
            "agent_name": "Test Agent for Run",
            "owner": 123,
            "owner_username": "run_owner",
            "organization": str(mock_org_id),
            "organization_name": "Test Org for Run",
            "timestamp": timestamp_str,
            "is_client_executed": True,
            "results": [mock_result_data_in_run],
            "attack": str(mock_attack_id),
            "run_config": {"detail": "run_specific_config"},
            "status": StatusEnum.COMPLETED.value,
            "run_notes": "Run completed successfully.",
        }
        mock_response_content = {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [mock_run_data],
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 200
        mock_httpx_response.json.return_value = mock_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_object = PaginatedRunList.model_validate(mock_response_content)

        with patch(
            "hackagent.api.run.run_list.PaginatedRunList.model_validate",
            return_value=mock_parsed_object,
        ) as mock_model_validate:
            response = run_list.sync_detailed(
                client=mock_client_instance,
                agent=mock_agent_id,
                attack=mock_attack_id,
                organization=mock_org_id,
                status=StatusEnum.COMPLETED,  # Use StatusEnum for filter
                page=1,
            )

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.count, 1)
            self.assertTrue(
                isinstance(response.parsed.results, list)
                and len(response.parsed.results) > 0
            )

            retrieved_run = response.parsed.results[0]
            self.assertEqual(retrieved_run.id, mock_run_id)
            self.assertEqual(retrieved_run.agent, mock_agent_id)
            self.assertEqual(retrieved_run.organization, mock_org_id)
            self.assertEqual(
                retrieved_run.status, StatusEnum.COMPLETED
            )  # Run.status is StatusEnum
            self.assertEqual(retrieved_run.timestamp, isoparse(timestamp_str))
            self.assertTrue(
                isinstance(retrieved_run.results, list)
                and len(retrieved_run.results) > 0
            )
            self.assertEqual(retrieved_run.results[0].id, mock_result_id_in_run)
            self.assertEqual(
                retrieved_run.results[0].run_id, mock_run_id
            )  # Check nested Result's run_id

            mock_model_validate.assert_called_once_with(mock_response_content)

            expected_params = {
                "agent": str(mock_agent_id),
                "attack": str(mock_attack_id),
                "organization": str(mock_org_id),
                "status": StatusEnum.COMPLETED.value,
                "page": 1,
                # is_client_executed is not passed if UNSET (default) but we can test it if needed
            }
            actual_call_kwargs = mock_httpx_client.request.call_args.kwargs
            self.assertEqual(actual_call_kwargs["method"], "get")
            self.assertEqual(actual_call_kwargs["url"], "/run")
            # Filter out UNSET params before comparing, as they are not sent
            sent_params = {
                k: v for k, v in actual_call_kwargs["params"].items() if v is not UNSET
            }
            self.assertDictEqual(sent_params, expected_params)

    @patch("hackagent.api.run.run_list.AuthenticatedClient")
    def test_run_list_sync_detailed_error_raise_on_unexpected_status_true(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 500
        mock_httpx_response.content = b"Server Error For Run List"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            run_list.sync_detailed(client=mock_client_instance)

        self.assertEqual(cm.exception.status_code, 500)
        self.assertEqual(cm.exception.content, b"Server Error For Run List")

    @patch("hackagent.api.run.run_list.AuthenticatedClient")
    def test_run_list_sync_detailed_error_raise_on_unexpected_status_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 403  # Forbidden
        mock_httpx_response.content = b"Forbidden Access to Run List"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = run_list.sync_detailed(client=mock_client_instance)

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIsNone(response.parsed)


class TestRunCreateAPI(unittest.TestCase):
    @patch("hackagent.api.run.run_create.AuthenticatedClient")
    def test_run_create_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        mock_agent_id_create = uuid.uuid4()
        mock_attack_id_create = uuid.uuid4()

        run_request_data = RunRequest(
            agent=mock_agent_id_create,
            attack=mock_attack_id_create,
            run_config={"setting": "value"},
            status=StatusEnum.PENDING,
            run_notes="Initial notes for run creation.",
        )

        mock_created_run_id = uuid.uuid4()
        timestamp_create_str = "2023-09-02T10:00:00Z"
        mock_org_id_create_resp = uuid.uuid4()

        # For a created Run, results list is usually empty initially
        mock_response_content = {
            "id": str(mock_created_run_id),
            "agent": str(run_request_data.agent),
            "agent_name": "Agent Name For Created Run",  # Server populates
            "owner": 456,
            "owner_username": "creator_user",
            "organization": str(mock_org_id_create_resp),
            "organization_name": "Org For Created Run",
            "timestamp": timestamp_create_str,  # Server sets this
            "is_client_executed": False,  # Default for direct creation might be False
            "results": [],  # Initially empty
            "attack": str(run_request_data.attack) if run_request_data.attack else None,
            "run_config": run_request_data.run_config,
            "status": run_request_data.status.value
            if run_request_data.status
            else None,
            "run_notes": run_request_data.run_notes,
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 201  # Created
        mock_httpx_response.json.return_value = mock_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_run = Run.model_validate(mock_response_content)

        with patch(
            "hackagent.api.run.run_create.Run.model_validate", return_value=mock_parsed_run
        ) as mock_model_validate:
            response = run_create.sync_detailed(
                client=mock_client_instance, body=run_request_data
            )

            self.assertEqual(response.status_code, HTTPStatus.CREATED)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.id, mock_created_run_id)
            self.assertEqual(response.parsed.agent, run_request_data.agent)
            self.assertEqual(response.parsed.status, run_request_data.status)
            self.assertEqual(response.parsed.run_config, run_request_data.run_config)
            self.assertEqual(len(response.parsed.results), 0)  # Check for empty results

            mock_model_validate.assert_called_once_with(mock_response_content)

            expected_kwargs = {
                "method": "post",
                "url": "/run",
                "json": run_request_data.model_dump(by_alias=True, mode="json", exclude_none=True),
                "headers": {"Content-Type": "application/json"},
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.run.run_create.AuthenticatedClient")
    def test_run_create_sync_detailed_error_raise_on_unexpected_status_true(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        # Agent ID is mandatory for RunRequest
        error_request_data = RunRequest(
            agent=uuid.uuid4(),
            run_notes="bad data missing fields potentially expected by server logic though optional in model",
        )

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 400
        mock_httpx_response.content = b"Bad Run Request Data"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            run_create.sync_detailed(
                client=mock_client_instance, body=error_request_data
            )

        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(cm.exception.content, b"Bad Run Request Data")

    @patch("hackagent.api.run.run_create.AuthenticatedClient")
    def test_run_create_sync_detailed_error_raise_on_unexpected_status_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        error_request_data_false = RunRequest(
            agent=uuid.uuid4(), status=StatusEnum.RUNNING
        )  # Example

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 401  # e.g. Unauthorized
        mock_httpx_response.content = b"Unauthorized Run Creation"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = run_create.sync_detailed(
            client=mock_client_instance, body=error_request_data_false
        )

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
        self.assertIsNone(response.parsed)


class TestRunRetrieveAPI(unittest.TestCase):
    @patch("hackagent.api.run.run_retrieve.AuthenticatedClient")
    def test_run_retrieve_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        run_id_to_retrieve = uuid.uuid4()
        mock_agent_id_retrieve = uuid.uuid4()
        mock_org_id_retrieve = uuid.uuid4()
        timestamp_retrieve_str = "2023-09-03T10:00:00Z"

        # Mock for a Result within the retrieved Run's results list
        mock_result_id_retrieve = uuid.uuid4()
        mock_trace_data_retrieve = {
            "id": 1,
            "result": str(mock_result_id_retrieve),
            "sequence": 1,
            "type": "INFO",
            "content": "Retrieved trace",
            "timestamp": timestamp_retrieve_str,
            "metadata": {},
        }
        mock_result_data_retrieve = {
            "id": str(mock_result_id_retrieve),
            "run": str(run_id_to_retrieve),
            "run_id": str(run_id_to_retrieve),
            "prompt_name": "Prompt in Retrieved Run's Result",
            "timestamp": timestamp_retrieve_str,
            "traces": [mock_trace_data_retrieve],
            "prompt": str(uuid.uuid4()),
            "evaluation_status": EvaluationStatusEnum.PASSED_CRITERIA.value,
            "response_body": "Response in Retrieved Run's Result",
        }

        mock_response_content = {
            "id": str(run_id_to_retrieve),
            "agent": str(mock_agent_id_retrieve),
            "agent_name": "Retrieved Agent",
            "owner": 789,
            "owner_username": "retrieved_owner",
            "organization": str(mock_org_id_retrieve),
            "organization_name": "Retrieved Org Name",
            "timestamp": timestamp_retrieve_str,
            "is_client_executed": False,
            "results": [mock_result_data_retrieve],
            "attack": None,  # Can be None
            "run_config": {"config_key": "retrieved_value"},
            "status": StatusEnum.RUNNING.value,
            "run_notes": "Run failed during execution.",
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 200
        mock_httpx_response.json.return_value = mock_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_run = Run.model_validate(mock_response_content)

        with patch(
            "hackagent.api.run.run_retrieve.Run.model_validate", return_value=mock_parsed_run
        ) as mock_model_validate:
            response = run_retrieve.sync_detailed(
                client=mock_client_instance, id=run_id_to_retrieve
            )

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.id, run_id_to_retrieve)
            self.assertEqual(response.parsed.agent, mock_agent_id_retrieve)
            self.assertEqual(response.parsed.status, StatusEnum.RUNNING)
            self.assertEqual(
                response.parsed.timestamp, isoparse(timestamp_retrieve_str)
            )
            self.assertTrue(len(response.parsed.results) > 0)
            self.assertEqual(
                response.parsed.results[0].traces[0].content, "Retrieved trace"
            )

            mock_model_validate.assert_called_once_with(mock_response_content)

            expected_kwargs = {
                "method": "get",
                "url": f"/run/{run_id_to_retrieve}",
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.run.run_retrieve.AuthenticatedClient")
    def test_run_retrieve_sync_detailed_error_not_found(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        run_id_not_found = uuid.uuid4()
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 404
        mock_httpx_response.content = b"Run Not Found"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            run_retrieve.sync_detailed(client=mock_client_instance, id=run_id_not_found)

        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.content, b"Run Not Found")

    @patch("hackagent.api.run.run_retrieve.AuthenticatedClient")
    def test_run_retrieve_sync_detailed_error_raise_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        run_id_error = uuid.uuid4()
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 500
        mock_httpx_response.content = b"Server Side Issue For Run Retrieve"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = run_retrieve.sync_detailed(
            client=mock_client_instance, id=run_id_error
        )

        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.assertIsNone(response.parsed)


class TestRunUpdateAPI(unittest.TestCase):
    @patch("hackagent.api.run.run_update.AuthenticatedClient")
    def test_run_update_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        run_id_to_update = uuid.uuid4()
        # For PUT, the RunRequest requires agent, other fields are optional but can be updated.
        mock_agent_id_for_update_body = uuid.uuid4()

        run_update_request_data = RunRequest(
            agent=mock_agent_id_for_update_body,  # Mandatory for RunRequest
            status=StatusEnum.FAILED,
            run_notes="Updated: Run has failed.",
            run_config={"new_setting": "updated_value"},
        )

        # Mock response content reflecting the update
        timestamp_update_str = (
            "2023-09-04T12:00:00Z"  # Timestamp of the update operation on the Run
        )
        original_run_timestamp_str = (
            "2023-09-04T10:00:00Z"  # Original creation timestamp of the Run
        )
        mock_org_id_update_resp = uuid.uuid4()

        # Results might or might not be affected/returned by an update operation on the Run itself.
        # Assuming they are returned and unchanged for this test if not part of RunRequest.
        mock_result_id_update = uuid.uuid4()
        mock_trace_data_update = {
            "id": 1,
            "result": str(mock_result_id_update),
            "sequence": 1,
            "type": "ERROR",
            "content": "Updated trace in result",
            "timestamp": timestamp_update_str,
            "metadata": {},
        }
        mock_result_data_update = {
            "id": str(mock_result_id_update),
            "run": str(run_id_to_update),
            "run_id": str(run_id_to_update),
            "prompt_name": "Prompt in Updated Run's Result",
            "timestamp": original_run_timestamp_str,  # Result timestamp is its own creation time
            "traces": [mock_trace_data_update],
            "prompt": str(uuid.uuid4()),
            "evaluation_status": EvaluationStatusEnum.ERROR_AGENT_RESPONSE.value,
            "response_body": "Updated response in Run's Result",
        }

        mock_updated_run_response_content = {
            "id": str(run_id_to_update),
            "agent": str(
                run_update_request_data.agent
            ),  # Should reflect the agent from request
            "agent_name": "Updated Agent Name",
            "owner": 111,
            "owner_username": "updater_user",
            "organization": str(mock_org_id_update_resp),
            "organization_name": "Org Name After Update",
            "timestamp": original_run_timestamp_str,  # Run creation timestamp should remain
            "is_client_executed": True,  # Assuming this field is not changed by this update
            "results": [
                mock_result_data_update
            ],  # Assume results are part of the response
            "attack": str(
                uuid.uuid4()
            ),  # Assuming this field is not changed or set if UNSET
            "run_config": run_update_request_data.run_config,  # Updated
            "status": run_update_request_data.status.value
            if run_update_request_data.status
            else None,  # Updated
            "run_notes": run_update_request_data.run_notes,  # Updated
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 200  # OK for successful update
        mock_httpx_response.json.return_value = mock_updated_run_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_run = Run.model_validate(mock_updated_run_response_content)

        with patch(
            "hackagent.api.run.run_update.Run.model_validate", return_value=mock_parsed_run
        ) as mock_model_validate:
            response = run_update.sync_detailed(
                client=mock_client_instance,
                id=run_id_to_update,
                body=run_update_request_data,
            )

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.id, run_id_to_update)
            self.assertEqual(response.parsed.status, run_update_request_data.status)
            self.assertEqual(
                response.parsed.run_notes, run_update_request_data.run_notes
            )
            self.assertEqual(
                response.parsed.run_config, run_update_request_data.run_config
            )
            self.assertEqual(response.parsed.agent, mock_agent_id_for_update_body)
            self.assertEqual(
                response.parsed.timestamp, isoparse(original_run_timestamp_str)
            )

            mock_model_validate.assert_called_once_with(mock_updated_run_response_content)

            expected_kwargs = {
                "method": "put",
                "url": f"/run/{run_id_to_update}",
                "json": run_update_request_data.model_dump(by_alias=True, mode="json", exclude_none=True),
                "headers": {"Content-Type": "application/json"},
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.run.run_update.AuthenticatedClient")
    def test_run_update_sync_detailed_error_not_found(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        run_id_not_found = uuid.uuid4()
        update_data = RunRequest(agent=uuid.uuid4(), run_notes="update fail not found")

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 404
        mock_httpx_response.content = b"Run Not Found For Update"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            run_update.sync_detailed(
                client=mock_client_instance, id=run_id_not_found, body=update_data
            )

        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.content, b"Run Not Found For Update")

    @patch("hackagent.api.run.run_update.AuthenticatedClient")
    def test_run_update_sync_detailed_error_raise_false(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        run_id_error_update = uuid.uuid4()
        # RunRequest agent field is mandatory for PUT body
        update_data_error = RunRequest(agent=uuid.uuid4(), status=StatusEnum.COMPLETED)

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 400  # Bad Request
        mock_httpx_response.content = b"Update Failed Validation - Run"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = run_update.sync_detailed(
            client=mock_client_instance, id=run_id_error_update, body=update_data_error
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIsNone(response.parsed)


class TestRunPartialUpdateAPI(unittest.TestCase):
    @patch("hackagent.api.run.run_partial_update.AuthenticatedClient")
    def test_run_partial_update_sync_detailed_success_patch_status_notes(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        run_id_to_patch = uuid.uuid4()

        run_patch_request_data = PatchedRunRequest(
            status=StatusEnum.RUNNING,
            run_notes="Run is now actively running after patch.",
        )

        # Mock response should reflect the patched fields and existing values for others
        mock_agent_id_patch_resp = uuid.uuid4()
        mock_org_id_patch_resp = uuid.uuid4()
        original_timestamp_patch_str = "2023-09-05T09:00:00Z"
        original_run_config_patch_resp = {"original_key": "original_value"}

        mock_patched_run_response_content = {
            "id": str(run_id_to_patch),
            "agent": str(mock_agent_id_patch_resp),  # Original/current agent
            "agent_name": "Agent Name Before Patch",
            "owner": 222,
            "owner_username": "patch_user",
            "organization": str(mock_org_id_patch_resp),
            "organization_name": "Org Name Before Patch",
            "timestamp": original_timestamp_patch_str,  # Original creation timestamp
            "is_client_executed": False,
            "results": [],  # Assuming results are not changed by this patch
            "attack": None,
            "run_config": original_run_config_patch_resp,  # Original config
            "status": run_patch_request_data.status.value
            if run_patch_request_data.status
            else None,  # Patched
            "run_notes": run_patch_request_data.run_notes,  # Patched
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 200  # OK for successful patch
        mock_httpx_response.json.return_value = mock_patched_run_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_run = Run.model_validate(mock_patched_run_response_content)

        with patch(
            "hackagent.api.run.run_partial_update.Run.model_validate",
            return_value=mock_parsed_run,
        ) as mock_model_validate:
            response = run_partial_update.sync_detailed(
                client=mock_client_instance,
                id=run_id_to_patch,
                body=run_patch_request_data,
            )

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.id, run_id_to_patch)
            self.assertEqual(response.parsed.status, run_patch_request_data.status)
            self.assertEqual(
                response.parsed.run_notes, run_patch_request_data.run_notes
            )
            self.assertEqual(
                response.parsed.run_config, original_run_config_patch_resp
            )  # Verify unpatched field

            mock_model_validate.assert_called_once_with(mock_patched_run_response_content)

            expected_kwargs = {
                "method": "patch",
                "url": f"/run/{run_id_to_patch}",
                "json": run_patch_request_data.model_dump(by_alias=True, mode="json", exclude_none=True),
                "headers": {"Content-Type": "application/json"},
            }
            request_dict = run_patch_request_data.model_dump(by_alias=True, mode="json", exclude_none=True)
            self.assertIn("status", request_dict)
            self.assertIn("run_notes", request_dict)
            self.assertIsNone(request_dict.get("run_config"))  # Unset optional fields serialize as None
            self.assertIsNone(request_dict.get("agent"))  # Unset optional fields serialize as None

            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.run.run_partial_update.AuthenticatedClient")
    def test_run_partial_update_sync_detailed_error_not_found(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        run_id_not_found = uuid.uuid4()
        patch_data = PatchedRunRequest(run_notes="Patch fail not found")

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 404
        mock_httpx_response.content = b"Run Not Found For Patch"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            run_partial_update.sync_detailed(
                client=mock_client_instance, id=run_id_not_found, body=patch_data
            )

        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.content, b"Run Not Found For Patch")

    @patch("hackagent.api.run.run_partial_update.AuthenticatedClient")
    def test_run_partial_update_sync_detailed_error_raise_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        run_id_error_patch = uuid.uuid4()
        patch_data_error = PatchedRunRequest(
            status=StatusEnum.FAILED
        )  # Example valid patch data

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 400  # Bad Request for other reasons
        mock_httpx_response.content = b"Patch Failed Validation - Run"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = run_partial_update.sync_detailed(
            client=mock_client_instance, id=run_id_error_patch, body=patch_data_error
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIsNone(response.parsed)


class TestRunDestroyAPI(unittest.TestCase):
    @patch("hackagent.api.run.run_destroy.AuthenticatedClient")
    def test_run_destroy_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        run_id_to_delete = uuid.uuid4()

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 204  # No Content for successful deletion
        mock_httpx_response.content = b""
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = run_destroy.sync_detailed(
            client=mock_client_instance, id=run_id_to_delete
        )

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        self.assertIsNone(response.parsed)  # No parsed content for 204

        expected_kwargs = {
            "method": "delete",
            "url": f"/run/{run_id_to_delete}",
        }
        mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.run.run_destroy.AuthenticatedClient")
    def test_run_destroy_sync_detailed_error_not_found(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        run_id_not_found_delete = uuid.uuid4()

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 404
        mock_httpx_response.content = b"Run Not Found For Deletion"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            run_destroy.sync_detailed(
                client=mock_client_instance, id=run_id_not_found_delete
            )

        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.content, b"Run Not Found For Deletion")

    @patch("hackagent.api.run.run_destroy.AuthenticatedClient")
    def test_run_destroy_sync_detailed_error_raise_false(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        run_id_error_delete = uuid.uuid4()

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 500  # Internal Server Error
        mock_httpx_response.content = b"Deletion Failed Server Side - Run"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = run_destroy.sync_detailed(
            client=mock_client_instance, id=run_id_error_delete
        )

        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.assertIsNone(response.parsed)


class TestRunResultCreateAPI(unittest.TestCase):
    @patch("hackagent.api.run.run_result_create.AuthenticatedClient")
    def test_run_result_create_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        parent_run_id = uuid.uuid4()
        mock_prompt_id_for_result = uuid.uuid4()

        # Body for creating a Result under a Run
        # The 'run' field in ResultRequest must match parent_run_id
        result_create_body = RunResultCreateRequest(
            run=parent_run_id,
            prompt=mock_prompt_id_for_result,
            request_payload={"input_data": "test input for new result"},
            response_body="Agent response for new result under run.",
            evaluation_status=EvaluationStatusEnum.PASSED_CRITERIA,
            evaluation_notes="New result passed criteria.",
        )

        mock_created_result_id = uuid.uuid4()
        timestamp_str_for_result = "2023-09-01T12:00:00Z"
        mock_trace_data_in_result_create = {
            "id": 789,  # Trace ID is int
            "result": str(mock_created_result_id),
            "sequence": 1,
            "type": "SYSTEM",
            "content": "Trace for newly created result under run",
            "timestamp": timestamp_str_for_result,
            "metadata": {},
        }

        # This is the content the server would return for the created Result.
        # It needs to be parsable by Result.model_validate
        mock_response_content_for_result = {
            "id": str(mock_created_result_id),
            "run": str(
                parent_run_id
            ),  # Ensure 'run' (UUID of parent Run) is present for Result.model_validate
            "run_id": str(parent_run_id),  # run_id is also an attribute of Result model
            "prompt_name": "Prompt For Newly Created Result Under Run",  # Server might derive this
            "timestamp": timestamp_str_for_result,
            "traces": [mock_trace_data_in_result_create],
            "prompt": str(result_create_body.prompt)
            if result_create_body.prompt
            else None,
            "request_payload": result_create_body.request_payload,
            "response_status_code": 200,  # Example
            "response_headers": {"Content-Type": "application/json"},  # Example
            "response_body": result_create_body.response_body,
            "latency_ms": result_create_body.latency_ms,
            "detected_tool_calls": [],
            "evaluation_status": result_create_body.evaluation_status.value
            if result_create_body.evaluation_status
            else None,
            "evaluation_notes": result_create_body.evaluation_notes,
            "evaluation_metrics": {},
            "agent_specific_data": {},
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 201  # POST create returns 201 Created
        mock_httpx_response.json.return_value = mock_response_content_for_result
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        # The run_result_create API returns a Result model instance
        mock_parsed_result_object = Result.model_validate(mock_response_content_for_result)
        # Ensure raise_on_unexpected_status is True for this success test if not default
        mock_client_instance.raise_on_unexpected_status = True

        with patch(
            "hackagent.api.run.run_result_create.Result.model_validate",
            return_value=mock_parsed_result_object,
        ) as mock_model_validate:
            response = run_result_create.sync_detailed(
                client=mock_client_instance,
                id=parent_run_id,  # This is the Run ID in the URL path
                body=result_create_body,
            )

            self.assertEqual(
                response.status_code, HTTPStatus.CREATED
            )  # POST create returns 201
            self.assertIsNotNone(response.parsed)
            self.assertIsInstance(
                response.parsed, Result
            )  # Ensure it's a Result object
            self.assertEqual(response.parsed.id, mock_created_result_id)
            self.assertEqual(
                response.parsed.run_id, parent_run_id
            )  # Check the run_id in the created Result
            self.assertEqual(
                response.parsed.evaluation_status, result_create_body.evaluation_status
            )

            mock_model_validate.assert_called_once_with(mock_response_content_for_result)

            expected_kwargs = {
                "method": "post",
                "url": f"/run/{parent_run_id}/result",
                "json": result_create_body.model_dump(by_alias=True, mode="json", exclude_none=True),
                "headers": {"Content-Type": "application/json"},
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.run.run_result_create.AuthenticatedClient")
    def test_run_result_create_sync_detailed_error_run_not_found(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        run_id_not_found = uuid.uuid4()
        # ResultRequest body needs a run UUID, even if it's for a non-existent parent run
        error_body = RunResultCreateRequest(run=run_id_not_found, response_body="test")

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 404  # Parent Run not found
        mock_httpx_response.content = b"Parent Run Not Found for Result Creation"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            run_result_create.sync_detailed(
                client=mock_client_instance, id=run_id_not_found, body=error_body
            )

        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(
            cm.exception.content, b"Parent Run Not Found for Result Creation"
        )

    @patch("hackagent.api.run.run_result_create.AuthenticatedClient")
    def test_run_result_create_sync_detailed_error_bad_request_raise_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        parent_run_id_bad_req = uuid.uuid4()
        # Missing mandatory 'run' field in ResultRequest or mismatched with path ID (server should catch this)
        # For this test, assume client sends a body for a *different* run_id than path.
        mismatched_run_id = uuid.uuid4()
        bad_body = RunResultCreateRequest(
            run=mismatched_run_id, response_body="mismatched run id in body"
        )

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 400
        mock_httpx_response.content = b"Bad Request for Result Creation under Run"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = run_result_create.sync_detailed(
            client=mock_client_instance, id=parent_run_id_bad_req, body=bad_body
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIsNone(response.parsed)


class TestRunRunTestsCreateAPI(unittest.TestCase):
    @patch("hackagent.api.run.run_run_tests_create.AuthenticatedClient")
    def test_run_run_tests_create_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = (
            False  # Adjusted for 201 and no parsing
        )

        # The API client for run_run_tests_create expects a RunRequest body
        # The ID parameter is for the run to associate tests with, but the endpoint is /api/run/run_tests (no ID in URL for POST)
        # The API spec for this custom action in run_run_tests_create.py shows it takes a RunRequest body.
        # Let's assume the 'id' parameter in the client function run_run_tests_create.sync_detailed is a typo
        # and is not actually used to construct the URL /api/run/{id}/run_tests, but rather the body is sent to /api/run/run_tests.
        # If the `id` is indeed used for the URL, then the `url` in expected_kwargs will need to change.
        # For now, matching the structure of other create operations that use POST to a collection URL.

        run_tests_request_body = RunRequest(agent=uuid.uuid4())

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 201  # As per original error message
        mock_httpx_response.json.return_value = {}  # Empty JSON body
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        # No specific model is parsed by the client for 201 if raise_on_unexpected_status is False
        response = run_run_tests_create.sync_detailed(
            client=mock_client_instance, body=run_tests_request_body
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertIsNone(
            response.parsed
        )  # Assert that parsed is None for 201 with current client logic

        expected_kwargs = {
            "method": "post",
            "url": "/run/run_tests",  # Matches _get_kwargs in the client file
            "json": run_tests_request_body.model_dump(by_alias=True, mode="json", exclude_none=True),
            "headers": {"Content-Type": "application/json"},
        }
        mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.run.run_run_tests_create.AuthenticatedClient")
    def test_run_run_tests_create_sync_detailed_error_bad_request(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        # This test was for a RunRequest.__init__() missing 'agent'
        # The run_run_tests_create.sync_detailed function in the client takes 'body: RunRequest'
        # It does NOT take an 'id' parameter according to the client file's signature for sync_detailed.
        # The original traceback showed TypeError for RunRequest init for this test, not for the API call itself.
        # So, this test is about passing a malformed RunRequest to the client function's `body`.
        # The client function `_get_kwargs` calls `body.model_dump(by_alias=True, mode="json", exclude_none=True)`. If body is not a proper RunRequest,
        # this could fail before an API call is even attempted, or if `agent` is missing and `to_dict` needs it.
        # However, RunRequest itself takes agent as a mandatory field in its __init__.
        # The TypeError was: RunRequest.__init__() missing 1 required positional argument: 'agent'
        # This means the RunRequest was being instantiated without 'agent' *before* being passed to sync_detailed.
        # Let's fix the instantiation of bad_run_request_data if the goal is to test server-side bad request.
        # If the goal is client-side validation (which pytest might not be for if it's about API testing),
        # then the error happens before API call.
        # Given the previous error was about missing `agent` for RunRequest, this test should simulate a bad *payload* to the server.
        # To do this, the body (RunRequest) must be validly constructible but result in a 400 from server.
        # For now, keeping the agent in RunRequest as it's mandatory for the type.
        # The previous error was likely in the call to RunRequest() in the test itself, not the API logic.

        bad_run_request_data = RunRequest(agent=uuid.uuid4())  # Must have agent
        # To make it a "bad request" for the *server*, we'd need to know what makes it bad.
        # For this test, we'll assume the server returns 400 for some reason with this validly structured request.

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 400
        mock_httpx_response.content = b"Bad Request for Run Tests Create"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            # The client function `run_run_tests_create.sync_detailed` does not take an `id` kwarg.
            # It takes `client` and `body`.
            run_run_tests_create.sync_detailed(
                client=mock_client_instance, body=bad_run_request_data
            )

        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(cm.exception.content, b"Bad Request for Run Tests Create")

    @patch("hackagent.api.run.run_run_tests_create.AuthenticatedClient")
    def test_run_run_tests_create_sync_detailed_error_server_error_raise_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        request_body = RunRequest(agent=uuid.uuid4())  # Valid body structure

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 500
        mock_httpx_response.content = b"Server Error on Run Tests Create"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        # The client function `run_run_tests_create.sync_detailed` does not take an `id` kwarg.
        response = run_run_tests_create.sync_detailed(
            client=mock_client_instance, body=request_body
        )

        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.assertIsNone(response.parsed)


if __name__ == "__main__":
    unittest.main()
