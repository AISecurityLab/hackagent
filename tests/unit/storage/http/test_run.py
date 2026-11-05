# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


import unittest
import uuid
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from dateutil.parser import isoparse

from hackagent.core import errors
from hackagent.storage._http.api.run import (
    run_destroy,
    run_list,
    run_partial_update,
    run_result_create,
    run_retrieve,
)
from hackagent.storage._http.api.models import (
    EvaluationStatusEnum,
)  # For nested Result.evaluation_status
from hackagent.storage._http.api.models import PaginatedRunSummaryList
from hackagent.storage._http.api.models import PatchedRunUpdateRequest
from hackagent.storage._http.api.models import Result  # For nested results within a Run
from hackagent.storage._http.api.models import (
    ResultRequest as RunResultCreateRequest,
)  # Alias to avoid confusion with main ResultRequest
from hackagent.storage._http.api.models import Run
from hackagent.storage._http.api.models import RunListStatus
from hackagent.storage._http.api.models import StatusEnum
from hackagent.storage._http.types import UNSET


class TestRunListAPI(unittest.TestCase):
    @patch("hackagent.storage._http.api.run.run_list.AuthenticatedClient")
    def test_run_list_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        mock_run_id = uuid.uuid4()
        mock_agent_id = uuid.uuid4()
        mock_org_id = uuid.uuid4()
        mock_attack_id = uuid.uuid4()
        timestamp_str = "2023-09-01T10:00:00Z"

        mock_run_data = {
            "id": str(mock_run_id),
            "agent": str(mock_agent_id),
            "agent_name": "Test Agent for Run",
            "owner": 123,
            "owner_username": "run_owner",
            "organization": str(mock_org_id),
            "organization_name": "Test Org for Run",
            "timestamp": timestamp_str,
            "executor": "cli",
            "campaign": None,
            "parent": None,
            "claimed_at": None,
            "claimed_by": "",
            "heartbeat_at": None,
            "cancel_requested_at": None,
            "finished_at": None,
            "attack_type": "baseline",
            "total_results": 1,
            "successful_jailbreaks": 0,
            "failed_jailbreaks": 0,
            "errors": 0,
            "not_evaluated": 1,
            "total_goals": 1,
            "jailbroken_goals": 0,
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

        mock_parsed_object = PaginatedRunSummaryList.model_validate(
            mock_response_content
        )

        with patch(
            "hackagent.storage._http.api.run.run_list.PaginatedRunSummaryList.model_validate",
            return_value=mock_parsed_object,
        ) as mock_model_validate:
            response = run_list.sync_detailed(
                client=mock_client_instance,
                agent=mock_agent_id,
                attack=mock_attack_id,
                organization=mock_org_id,
                status=RunListStatus.COMPLETED,
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
            self.assertEqual(retrieved_run.total_results, 1)
            self.assertEqual(retrieved_run.not_evaluated, 1)

            mock_model_validate.assert_called_once_with(mock_response_content)

            expected_params = {
                "agent": str(mock_agent_id),
                "attack": str(mock_attack_id),
                "organization": str(mock_org_id),
                "status": StatusEnum.COMPLETED.value,
                "page": 1,
            }
            actual_call_kwargs = mock_httpx_client.request.call_args.kwargs
            self.assertEqual(actual_call_kwargs["method"], "get")
            self.assertEqual(actual_call_kwargs["url"], "/run")
            # Filter out UNSET params before comparing, as they are not sent
            sent_params = {
                k: v for k, v in actual_call_kwargs["params"].items() if v is not UNSET
            }
            self.assertDictEqual(sent_params, expected_params)

    @patch("hackagent.storage._http.api.run.run_list.AuthenticatedClient")
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

    @patch("hackagent.storage._http.api.run.run_list.AuthenticatedClient")
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


class TestRunRetrieveAPI(unittest.TestCase):
    @patch("hackagent.storage._http.api.run.run_retrieve.AuthenticatedClient")
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
            "executor": "cli",
            "campaign": None,
            "parent": None,
            "claimed_at": None,
            "claimed_by": "",
            "heartbeat_at": None,
            "cancel_requested_at": None,
            "finished_at": None,
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
            "hackagent.storage._http.api.run.run_retrieve.Run.model_validate",
            return_value=mock_parsed_run,
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
                "params": {},
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.storage._http.api.run.run_retrieve.AuthenticatedClient")
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

    @patch("hackagent.storage._http.api.run.run_retrieve.AuthenticatedClient")
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


class TestRunPartialUpdateAPI(unittest.TestCase):
    @patch("hackagent.storage._http.api.run.run_partial_update.AuthenticatedClient")
    def test_run_partial_update_sync_detailed_success_patch_notes_and_config(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        run_id_to_patch = uuid.uuid4()

        run_patch_request_data = PatchedRunUpdateRequest(
            run_notes="Run is now actively running after patch.",
            run_config={"evaluation_audit": {"passed": True}},
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
            "executor": "cli",
            "campaign": None,
            "parent": None,
            "claimed_at": None,
            "claimed_by": "",
            "heartbeat_at": None,
            "cancel_requested_at": None,
            "finished_at": None,
            "results": [],  # Assuming results are not changed by this patch
            "attack": None,
            "run_config": original_run_config_patch_resp,  # Original config
            "status": StatusEnum.RUNNING.value,
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
            "hackagent.storage._http.api.run.run_partial_update.Run.model_validate",
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
            self.assertEqual(response.parsed.status, StatusEnum.RUNNING)
            self.assertEqual(
                response.parsed.run_notes, run_patch_request_data.run_notes
            )
            self.assertEqual(
                response.parsed.run_config, original_run_config_patch_resp
            )  # Verify unpatched field

            mock_model_validate.assert_called_once_with(
                mock_patched_run_response_content
            )

            expected_kwargs = {
                "method": "patch",
                "url": f"/run/{run_id_to_patch}",
                "json": run_patch_request_data.model_dump(
                    by_alias=True, mode="json", exclude_none=True
                ),
                "headers": {"Content-Type": "application/json"},
            }
            request_dict = run_patch_request_data.model_dump(
                by_alias=True, mode="json", exclude_none=True
            )
            # Status is read-only here: it changes only through the
            # executor endpoints.
            self.assertEqual(set(request_dict), {"run_notes", "run_config"})

            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.storage._http.api.run.run_partial_update.AuthenticatedClient")
    def test_run_partial_update_sync_detailed_error_not_found(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        run_id_not_found = uuid.uuid4()
        patch_data = PatchedRunUpdateRequest(run_notes="Patch fail not found")

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

    @patch("hackagent.storage._http.api.run.run_partial_update.AuthenticatedClient")
    def test_run_partial_update_sync_detailed_error_raise_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        run_id_error_patch = uuid.uuid4()
        patch_data_error = PatchedRunUpdateRequest(run_notes="Example valid patch")

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
    @patch("hackagent.storage._http.api.run.run_destroy.AuthenticatedClient")
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

    @patch("hackagent.storage._http.api.run.run_destroy.AuthenticatedClient")
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

    @patch("hackagent.storage._http.api.run.run_destroy.AuthenticatedClient")
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
    @patch("hackagent.storage._http.api.run.run_result_create.AuthenticatedClient")
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
            "timestamp": timestamp_str_for_result,
            "traces": [mock_trace_data_in_result_create],
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
        mock_parsed_result_object = Result.model_validate(
            mock_response_content_for_result
        )
        # Ensure raise_on_unexpected_status is True for this success test if not default
        mock_client_instance.raise_on_unexpected_status = True

        with patch(
            "hackagent.storage._http.api.run.run_result_create.Result.model_validate",
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

            mock_model_validate.assert_called_once_with(
                mock_response_content_for_result
            )

            expected_kwargs = {
                "method": "post",
                "url": f"/run/{parent_run_id}/result",
                "json": result_create_body.model_dump(
                    by_alias=True, mode="json", exclude_none=True
                ),
                "headers": {"Content-Type": "application/json"},
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.storage._http.api.run.run_result_create.AuthenticatedClient")
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

    @patch("hackagent.storage._http.api.run.run_result_create.AuthenticatedClient")
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


if __name__ == "__main__":
    unittest.main()
