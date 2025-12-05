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
from hackagent.api.result import (
    result_create,
    result_destroy,
    result_list,
    result_partial_update,
    result_retrieve,
    result_trace_create,
    result_update,
)
from hackagent.models.evaluation_status_enum import EvaluationStatusEnum
from hackagent.models.paginated_result_list import PaginatedResultList
from hackagent.models.patched_result_request import PatchedResultRequest
from hackagent.models.result import Result
from hackagent.models.result_request import ResultRequest
from hackagent.models.step_type_enum import (
    StepTypeEnum,
)  # Ensuring this import is present
from hackagent.models.trace import Trace
from hackagent.models.trace_request import TraceRequest  # For creating traces


class TestResultListAPI(unittest.TestCase):
    @patch("hackagent.api.result.result_list.AuthenticatedClient")
    def test_result_list_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        mock_result_id = uuid.uuid4()
        mock_run_id = uuid.uuid4()
        mock_prompt_id = uuid.uuid4()
        timestamp_str = "2023-08-01T10:00:00Z"

        # This is the mock_trace_data used in the list
        mock_trace_data_id_int = 123  # Using an int for trace ID
        mock_trace_data = {
            "id": mock_trace_data_id_int,
            "result": str(mock_result_id),
            "sequence": 1,
            "type_": "SYSTEM",
            "content": "Initial trace for result list",
            "timestamp": timestamp_str,
            "metadata": {},
        }

        mock_result_data = {
            "id": str(mock_result_id),
            "run": str(
                mock_run_id
            ),  # This field seems to be the same as run_id in the model but API might use 'run'
            "run_id": str(mock_run_id),  # Present in Result model
            "prompt_name": "Test Prompt For Result",
            "timestamp": timestamp_str,
            "traces": [mock_trace_data],
            "prompt": str(mock_prompt_id),
            "request_payload": {"input": "hello"},
            "response_status_code": 200,
            "response_headers": {"X-Test": "header"},
            "response_body": "Agent response here.",
            "latency_ms": 150,
            "detected_tool_calls": [],
            "evaluation_status": EvaluationStatusEnum.NOT_EVALUATED.value,  # Use enum value
            "evaluation_notes": "Initial result, not evaluated.",
            "evaluation_metrics": {"accuracy": 0.9},
            "agent_specific_data": {"mood": "happy"},
        }
        mock_response_content = {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [mock_result_data],
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 200
        mock_httpx_response.json.return_value = mock_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_object = PaginatedResultList.from_dict(mock_response_content)

        with patch(
            "hackagent.api.result.result_list.PaginatedResultList.from_dict",
            return_value=mock_parsed_object,
        ) as mock_from_dict:
            response = result_list.sync_detailed(
                client=mock_client_instance,
                run=mock_run_id,
                evaluation_status=EvaluationStatusEnum.NOT_EVALUATED,
                page=1,
            )

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.count, 1)
            self.assertTrue(
                isinstance(response.parsed.results, list)
                and len(response.parsed.results) > 0
            )

            retrieved_result = response.parsed.results[0]
            self.assertEqual(retrieved_result.id, mock_result_id)
            self.assertEqual(retrieved_result.run_id, mock_run_id)
            # self.assertEqual(retrieved_result.run, mock_run_id) # Check if 'run' attribute exists after from_dict
            self.assertEqual(retrieved_result.prompt_name, "Test Prompt For Result")
            self.assertEqual(retrieved_result.timestamp, isoparse(timestamp_str))
            self.assertTrue(
                isinstance(retrieved_result.traces, list)
                and len(retrieved_result.traces) > 0
            )
            self.assertEqual(
                retrieved_result.traces[0].id, mock_trace_data_id_int
            )  # Compare with int ID
            self.assertEqual(
                retrieved_result.evaluation_status, EvaluationStatusEnum.NOT_EVALUATED
            )

            mock_from_dict.assert_called_once_with(mock_response_content)

            expected_params = {
                "run": str(mock_run_id),
                "evaluation_status": EvaluationStatusEnum.NOT_EVALUATED.value,
                "page": 1,
            }
            # Remove UNSET params as they are not sent if default
            # json_prompt, json_run_organization are not passed, so they'd be UNSET
            actual_call_kwargs = mock_httpx_client.request.call_args.kwargs
            self.assertEqual(actual_call_kwargs["method"], "get")
            self.assertEqual(actual_call_kwargs["url"], "/result")
            self.assertDictEqual(actual_call_kwargs["params"], expected_params)

    @patch("hackagent.api.result.result_list.AuthenticatedClient")
    def test_result_list_sync_detailed_error_raise_on_unexpected_status_true(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 500
        mock_httpx_response.content = b"Server Error For Result List"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            result_list.sync_detailed(client=mock_client_instance)

        self.assertEqual(cm.exception.status_code, 500)
        self.assertEqual(cm.exception.content, b"Server Error For Result List")

    @patch("hackagent.api.result.result_list.AuthenticatedClient")
    def test_result_list_sync_detailed_error_raise_on_unexpected_status_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 403  # Forbidden
        mock_httpx_response.content = b"Forbidden Access to Result List"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = result_list.sync_detailed(client=mock_client_instance)

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIsNone(response.parsed)


class TestResultCreateAPI(unittest.TestCase):
    @patch("hackagent.api.result.result_create.AuthenticatedClient")
    def test_result_create_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        mock_run_id_create = uuid.uuid4()
        mock_prompt_id_create = uuid.uuid4()

        result_request_data = ResultRequest(
            run=mock_run_id_create,
            prompt=mock_prompt_id_create,
            request_payload={"data": "sample request"},
            response_body="Sample agent response for creation.",
            latency_ms=200,
            evaluation_status=EvaluationStatusEnum.PASSED_CRITERIA,
            evaluation_notes="Created and passed.",
        )

        mock_created_result_id = uuid.uuid4()
        timestamp_create_str = "2023-08-02T10:00:00Z"
        # Mock for Trace, assuming created result might have an initial trace or empty list
        mock_trace_data_create = {
            "id": str(uuid.uuid4()),
            "result": str(mock_created_result_id),
            "sequence": 1,
            "type_": "SYSTEM",
            "content": "Result created",
            "timestamp": timestamp_create_str,
            "metadata": {},
        }

        mock_response_content = {
            "id": str(mock_created_result_id),
            "run": str(result_request_data.run),  # Should match request
            "run_id": str(result_request_data.run),  # Model uses run_id
            "prompt_name": "Prompt For Created Result",  # Server might populate this based on prompt ID
            "timestamp": timestamp_create_str,  # Server sets this
            "traces": [mock_trace_data_create],  # Server might add an initial trace
            "prompt": str(result_request_data.prompt)
            if result_request_data.prompt
            else None,
            "request_payload": result_request_data.request_payload,
            "response_status_code": 200,  # Assuming default or server determined
            "response_headers": {"Content-Type": "application/json"},  # Example headers
            "response_body": result_request_data.response_body,
            "latency_ms": result_request_data.latency_ms,
            "detected_tool_calls": [],  # Assuming empty for this test
            "evaluation_status": result_request_data.evaluation_status.value
            if result_request_data.evaluation_status
            else None,
            "evaluation_notes": result_request_data.evaluation_notes,
            "evaluation_metrics": {},
            "agent_specific_data": {},
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 201  # Created
        mock_httpx_response.json.return_value = mock_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_result = Result.from_dict(mock_response_content)

        with patch(
            "hackagent.api.result.result_create.Result.from_dict",
            return_value=mock_parsed_result,
        ) as mock_from_dict:
            response = result_create.sync_detailed(
                client=mock_client_instance, body=result_request_data
            )

            self.assertEqual(response.status_code, HTTPStatus.CREATED)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.id, mock_created_result_id)
            self.assertEqual(response.parsed.run_id, result_request_data.run)
            self.assertEqual(
                response.parsed.evaluation_status, result_request_data.evaluation_status
            )
            self.assertEqual(
                response.parsed.response_body, result_request_data.response_body
            )

            mock_from_dict.assert_called_once_with(mock_response_content)

            expected_kwargs = {
                "method": "post",
                "url": "/result",
                "json": result_request_data.to_dict(),
                "headers": {"Content-Type": "application/json"},
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.result.result_create.AuthenticatedClient")
    def test_result_create_sync_detailed_error_raise_on_unexpected_status_true(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        # Run ID is mandatory for ResultRequest
        error_request_data = ResultRequest(
            run=uuid.uuid4(), evaluation_notes="bad data"
        )

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 400
        mock_httpx_response.content = b"Bad Result Request Data"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            result_create.sync_detailed(
                client=mock_client_instance, body=error_request_data
            )

        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(cm.exception.content, b"Bad Result Request Data")

    @patch("hackagent.api.result.result_create.AuthenticatedClient")
    def test_result_create_sync_detailed_error_raise_on_unexpected_status_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        error_request_data_false = ResultRequest(
            run=uuid.uuid4(), latency_ms=-100
        )  # Invalid data

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 401  # e.g. Unauthorized
        mock_httpx_response.content = b"Unauthorized Result Creation"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = result_create.sync_detailed(
            client=mock_client_instance, body=error_request_data_false
        )

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
        self.assertIsNone(response.parsed)


class TestResultRetrieveAPI(unittest.TestCase):
    @patch("hackagent.api.result.result_retrieve.AuthenticatedClient")
    def test_result_retrieve_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        result_id_to_retrieve = uuid.uuid4()
        mock_run_id_retrieve = uuid.uuid4()
        timestamp_retrieve_str = "2023-08-03T10:00:00Z"
        mock_trace_data_retrieve = {
            "id": str(uuid.uuid4()),
            "result": str(result_id_to_retrieve),
            "sequence": 1,
            "type_": "AGENT_ACTION",
            "content": "Agent took action",
            "timestamp": timestamp_retrieve_str,
            "metadata": {"action": "tool_call"},
        }

        mock_response_content = {
            "id": str(result_id_to_retrieve),
            "run": str(mock_run_id_retrieve),  # API might return 'run' field
            "run_id": str(mock_run_id_retrieve),  # Model has 'run_id'
            "prompt_name": "Retrieved Result's Prompt",
            "timestamp": timestamp_retrieve_str,
            "traces": [mock_trace_data_retrieve],
            "prompt": str(uuid.uuid4()),  # Example prompt ID
            "evaluation_status": EvaluationStatusEnum.SUCCESSFUL_JAILBREAK.value,
            "response_body": "Successfully jailbroken!",
            # ... other fields can be populated as needed for assertion
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 200
        mock_httpx_response.json.return_value = mock_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_result = Result.from_dict(mock_response_content)

        with patch(
            "hackagent.api.result.result_retrieve.Result.from_dict",
            return_value=mock_parsed_result,
        ) as mock_from_dict:
            response = result_retrieve.sync_detailed(
                client=mock_client_instance, id=result_id_to_retrieve
            )

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.id, result_id_to_retrieve)
            self.assertEqual(response.parsed.run_id, mock_run_id_retrieve)
            self.assertEqual(
                response.parsed.evaluation_status,
                EvaluationStatusEnum.SUCCESSFUL_JAILBREAK,
            )
            self.assertTrue(len(response.parsed.traces) > 0)

            mock_from_dict.assert_called_once_with(mock_response_content)

            expected_kwargs = {
                "method": "get",
                "url": f"/result/{result_id_to_retrieve}",
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.result.result_retrieve.AuthenticatedClient")
    def test_result_retrieve_sync_detailed_error_not_found(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        result_id_not_found = uuid.uuid4()
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 404
        mock_httpx_response.content = b"Result Not Found"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            result_retrieve.sync_detailed(
                client=mock_client_instance, id=result_id_not_found
            )

        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.content, b"Result Not Found")

    @patch("hackagent.api.result.result_retrieve.AuthenticatedClient")
    def test_result_retrieve_sync_detailed_error_raise_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        result_id_error = uuid.uuid4()
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 500
        mock_httpx_response.content = b"Server Side Issue For Result Retrieve"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = result_retrieve.sync_detailed(
            client=mock_client_instance, id=result_id_error
        )

        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.assertIsNone(response.parsed)


class TestResultUpdateAPI(unittest.TestCase):
    @patch("hackagent.api.result.result_update.AuthenticatedClient")
    def test_result_update_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        result_id_to_update = uuid.uuid4()
        mock_run_id_update = uuid.uuid4()  # Run ID for the request body

        result_update_request_data = ResultRequest(
            run=mock_run_id_update,  # Mandatory
            evaluation_status=EvaluationStatusEnum.FAILED_JAILBREAK,
            evaluation_notes="Updated: Now considered a failed jailbreak.",
            response_body="Agent refused after update.",
            # Other fields like prompt, request_payload can be included if they are updatable
        )

        # Mock response content reflecting the update
        timestamp_update_str = "2023-08-04T12:00:00Z"  # Timestamp of the update
        original_timestamp_str = (
            "2023-08-04T10:00:00Z"  # Original timestamp from creation
        )
        mock_trace_data_update = {
            "id": str(uuid.uuid4()),
            "result": str(result_id_to_update),
            "sequence": 1,
            "type_": "EVALUATION",
            "content": "Evaluation updated",
            "timestamp": timestamp_update_str,
            "metadata": {},
        }

        mock_updated_result_response_content = {
            "id": str(result_id_to_update),
            "run": str(result_update_request_data.run),
            "run_id": str(result_update_request_data.run),
            "prompt_name": "Updated Result's Prompt",
            "timestamp": original_timestamp_str,  # Timestamp of creation should remain
            "traces": [mock_trace_data_update],  # Traces might be updated or appended
            "prompt": str(uuid.uuid4()),  # Assuming it was set or remains
            "request_payload": {
                "input": "original input"
            },  # Assuming not changed by this update
            "response_status_code": 200,
            "response_headers": {"X-Test": "updated-header"},
            "response_body": result_update_request_data.response_body,
            "latency_ms": 250,
            "detected_tool_calls": None,
            "evaluation_status": result_update_request_data.evaluation_status.value
            if result_update_request_data.evaluation_status
            else None,
            "evaluation_notes": result_update_request_data.evaluation_notes,
            "evaluation_metrics": {"mitigation_score": 0.8},
            "agent_specific_data": {"state": "analyzed"},
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 200  # OK for successful update
        mock_httpx_response.json.return_value = mock_updated_result_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_result = Result.from_dict(mock_updated_result_response_content)

        with patch(
            "hackagent.api.result.result_update.Result.from_dict",
            return_value=mock_parsed_result,
        ) as mock_from_dict:
            response = result_update.sync_detailed(
                client=mock_client_instance,
                id=result_id_to_update,
                body=result_update_request_data,
            )

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.id, result_id_to_update)
            self.assertEqual(
                response.parsed.evaluation_status,
                result_update_request_data.evaluation_status,
            )
            self.assertEqual(
                response.parsed.evaluation_notes,
                result_update_request_data.evaluation_notes,
            )
            self.assertEqual(
                response.parsed.response_body, result_update_request_data.response_body
            )
            # The main Result timestamp should be creation, traces might have update timestamps
            self.assertEqual(
                response.parsed.timestamp, isoparse(original_timestamp_str)
            )

            mock_from_dict.assert_called_once_with(mock_updated_result_response_content)

            expected_kwargs = {
                "method": "put",
                "url": f"/result/{result_id_to_update}",
                "json": result_update_request_data.to_dict(),
                "headers": {"Content-Type": "application/json"},
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.result.result_update.AuthenticatedClient")
    def test_result_update_sync_detailed_error_not_found(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        result_id_not_found = uuid.uuid4()
        update_data = ResultRequest(run=uuid.uuid4(), evaluation_notes="update fail")

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 404
        mock_httpx_response.content = b"Result Not Found For Update"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            result_update.sync_detailed(
                client=mock_client_instance, id=result_id_not_found, body=update_data
            )

        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.content, b"Result Not Found For Update")

    @patch("hackagent.api.result.result_update.AuthenticatedClient")
    def test_result_update_sync_detailed_error_raise_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        result_id_error_update = uuid.uuid4()
        update_data_error = ResultRequest(
            run=uuid.uuid4(), response_status_code=999
        )  # Invalid status

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 400  # Bad Request
        mock_httpx_response.content = b"Update Failed Validation - Result"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = result_update.sync_detailed(
            client=mock_client_instance,
            id=result_id_error_update,
            body=update_data_error,
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIsNone(response.parsed)


class TestResultPartialUpdateAPI(unittest.TestCase):
    @patch("hackagent.api.result.result_partial_update.AuthenticatedClient")
    def test_result_partial_update_sync_detailed_success_patch_evaluation(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        result_id_to_patch = uuid.uuid4()

        result_patch_request_data = PatchedResultRequest(
            evaluation_status=EvaluationStatusEnum.ERROR_AGENT_RESPONSE,
            evaluation_notes="Patched: Agent response was an error.",
            evaluation_metrics={"error_code": 502},
        )

        # Mock response should reflect the patched fields and existing values for others
        mock_run_id_patch_resp = uuid.uuid4()
        original_timestamp_patch_str = "2023-08-05T09:00:00Z"
        # Traces might be complex, for patch, often the system creates a new trace or updates an existing one.
        # For simplicity, assume the response returns the state after patch.
        mock_trace_data_patch_resp = {
            "id": str(uuid.uuid4()),
            "result": str(result_id_to_patch),
            "sequence": 1,
            "type_": "EVALUATION",
            "content": "Evaluation patched for error",
            "timestamp": "2023-08-05T14:00:00Z",
            "metadata": {},
        }

        mock_patched_result_response_content = {
            "id": str(result_id_to_patch),
            "run": str(mock_run_id_patch_resp),  # Original/current run
            "run_id": str(mock_run_id_patch_resp),
            "prompt_name": "Result Before Patch Prompt Name",
            "timestamp": original_timestamp_patch_str,  # Original creation timestamp
            "traces": [mock_trace_data_patch_resp],
            "prompt": str(uuid.uuid4()),  # Original/current prompt
            "request_payload": {"original": "payload"},
            "response_status_code": 200,  # Original status
            "response_headers": {"X-Original": "value"},
            "response_body": "Original agent response before patch.",  # Original body
            "latency_ms": 100,  # Original latency
            "detected_tool_calls": [],
            "evaluation_status": result_patch_request_data.evaluation_status.value
            if result_patch_request_data.evaluation_status
            else None,  # Patched
            "evaluation_notes": result_patch_request_data.evaluation_notes,  # Patched
            "evaluation_metrics": result_patch_request_data.evaluation_metrics,  # Patched
            "agent_specific_data": {"original": "data"},
        }
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 200  # OK for successful patch
        mock_httpx_response.json.return_value = mock_patched_result_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_result = Result.from_dict(mock_patched_result_response_content)

        with patch(
            "hackagent.api.result.result_partial_update.Result.from_dict",
            return_value=mock_parsed_result,
        ) as mock_from_dict:
            response = result_partial_update.sync_detailed(
                client=mock_client_instance,
                id=result_id_to_patch,
                body=result_patch_request_data,
            )

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.id, result_id_to_patch)
            self.assertEqual(
                response.parsed.evaluation_status,
                result_patch_request_data.evaluation_status,
            )
            self.assertEqual(
                response.parsed.evaluation_notes,
                result_patch_request_data.evaluation_notes,
            )
            self.assertEqual(
                response.parsed.evaluation_metrics,
                result_patch_request_data.evaluation_metrics,
            )
            self.assertEqual(
                response.parsed.response_body, "Original agent response before patch."
            )  # Verify unpatched field

            mock_from_dict.assert_called_once_with(mock_patched_result_response_content)

            expected_kwargs = {
                "method": "patch",
                "url": f"/result/{result_id_to_patch}",
                "json": result_patch_request_data.to_dict(),
                "headers": {"Content-Type": "application/json"},
            }
            request_dict = result_patch_request_data.to_dict()
            self.assertIn("evaluation_status", request_dict)
            self.assertIn("evaluation_notes", request_dict)
            self.assertIn("evaluation_metrics", request_dict)
            self.assertNotIn("response_body", request_dict)

            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.result.result_partial_update.AuthenticatedClient")
    def test_result_partial_update_sync_detailed_error_not_found(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        result_id_not_found = uuid.uuid4()
        patch_data = PatchedResultRequest(evaluation_notes="Patch fail not found")

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 404
        mock_httpx_response.content = b"Result Not Found For Patch"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            result_partial_update.sync_detailed(
                client=mock_client_instance, id=result_id_not_found, body=patch_data
            )

        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.content, b"Result Not Found For Patch")

    @patch("hackagent.api.result.result_partial_update.AuthenticatedClient")
    def test_result_partial_update_sync_detailed_error_raise_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        result_id_error_patch = uuid.uuid4()
        patch_data_error = PatchedResultRequest(
            response_body="Trying to patch with error"
        )

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 400  # Bad Request
        mock_httpx_response.content = b"Patch Failed Validation - Result"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = result_partial_update.sync_detailed(
            client=mock_client_instance, id=result_id_error_patch, body=patch_data_error
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIsNone(response.parsed)


class TestResultDestroyAPI(unittest.TestCase):
    @patch("hackagent.api.result.result_destroy.AuthenticatedClient")
    def test_result_destroy_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        result_id_to_delete = uuid.uuid4()

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 204  # No Content for successful deletion
        mock_httpx_response.content = b""
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = result_destroy.sync_detailed(
            client=mock_client_instance, id=result_id_to_delete
        )

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        self.assertIsNone(response.parsed)  # No parsed content for 204

        expected_kwargs = {
            "method": "delete",
            "url": f"/result/{result_id_to_delete}",
        }
        mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.result.result_destroy.AuthenticatedClient")
    def test_result_destroy_sync_detailed_error_not_found(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        result_id_not_found_delete = uuid.uuid4()

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 404
        mock_httpx_response.content = b"Result Not Found For Deletion"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            result_destroy.sync_detailed(
                client=mock_client_instance, id=result_id_not_found_delete
            )

        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.content, b"Result Not Found For Deletion")

    @patch("hackagent.api.result.result_destroy.AuthenticatedClient")
    def test_result_destroy_sync_detailed_error_raise_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        result_id_error_delete = uuid.uuid4()

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 500  # Internal Server Error
        mock_httpx_response.content = b"Deletion Failed Server Side - Result"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = result_destroy.sync_detailed(
            client=mock_client_instance, id=result_id_error_delete
        )

        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.assertIsNone(response.parsed)


class TestResultTraceCreateAPI(unittest.TestCase):
    @patch("hackagent.api.result.result_trace_create.AuthenticatedClient")
    def test_result_trace_create_sync_detailed_success(self, MockAuthenticatedClient):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client

        result_id_for_trace = uuid.uuid4()
        trace_request_data = TraceRequest(
            sequence=1,
            step_type=StepTypeEnum.AGENT_THOUGHT,
            content={"thought": "I should call a tool."},
        )

        mock_created_trace_id = 99  # Trace ID is int
        timestamp_trace_create_str = "2023-08-06T10:00:00Z"

        mock_response_content = {
            "id": mock_created_trace_id,
            "result": str(result_id_for_trace),  # Should match the parent result ID
            "sequence": trace_request_data.sequence,
            "step_type": trace_request_data.step_type.value
            if trace_request_data.step_type
            else None,
            "content": trace_request_data.content,
            "timestamp": timestamp_trace_create_str,  # Server sets this
        }
        mock_httpx_response = MagicMock()
        # Typical status for creating a sub-resource or action could be 200 or 201
        # The API file result_trace_create.py _parse_response expects 200 for Trace.from_dict
        mock_httpx_response.status_code = 200
        mock_httpx_response.json.return_value = mock_response_content
        mock_httpx_response.content = b"{}"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        mock_parsed_trace = Trace.from_dict(mock_response_content)

        with patch(
            "hackagent.api.result.result_trace_create.Trace.from_dict",
            return_value=mock_parsed_trace,
        ) as mock_from_dict:
            response = result_trace_create.sync_detailed(
                client=mock_client_instance,
                id=result_id_for_trace,
                body=trace_request_data,
            )

            self.assertEqual(
                response.status_code, HTTPStatus.OK
            )  # Matching the parse logic
            self.assertIsNotNone(response.parsed)
            self.assertEqual(response.parsed.id, mock_created_trace_id)
            self.assertEqual(response.parsed.result, result_id_for_trace)
            self.assertEqual(response.parsed.sequence, trace_request_data.sequence)
            self.assertEqual(response.parsed.step_type, trace_request_data.step_type)

            mock_from_dict.assert_called_once_with(mock_response_content)

            expected_kwargs = {
                "method": "post",
                "url": f"/result/{result_id_for_trace}/trace",
                "json": trace_request_data.to_dict(),
                "headers": {"Content-Type": "application/json"},
            }
            mock_httpx_client.request.assert_called_once_with(**expected_kwargs)

    @patch("hackagent.api.result.result_trace_create.AuthenticatedClient")
    def test_result_trace_create_sync_detailed_error_result_not_found(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = True

        result_id_not_found = uuid.uuid4()
        trace_request_data = TraceRequest(sequence=1, content="test")

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 404  # Result not found
        mock_httpx_response.content = b"Parent Result Not Found For Trace Creation"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        with self.assertRaises(errors.UnexpectedStatusError) as cm:
            result_trace_create.sync_detailed(
                client=mock_client_instance,
                id=result_id_not_found,
                body=trace_request_data,
            )

        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(
            cm.exception.content, b"Parent Result Not Found For Trace Creation"
        )

    @patch("hackagent.api.result.result_trace_create.AuthenticatedClient")
    def test_result_trace_create_sync_detailed_error_bad_request_raise_false(
        self, MockAuthenticatedClient
    ):
        mock_client_instance = MockAuthenticatedClient.return_value
        mock_httpx_client = MagicMock()
        mock_client_instance.get_httpx_client.return_value = mock_httpx_client
        mock_client_instance.raise_on_unexpected_status = False

        result_id_for_bad_trace = uuid.uuid4()
        # Missing mandatory 'sequence' field in TraceRequest
        bad_trace_request_data = TraceRequest(step_type=StepTypeEnum.OTHER, sequence=1)

        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 400
        mock_httpx_response.content = b"Bad Trace Request Data"
        mock_httpx_response.headers = {}
        mock_httpx_client.request.return_value = mock_httpx_response

        response = result_trace_create.sync_detailed(
            client=mock_client_instance,
            id=result_id_for_bad_trace,
            body=bad_trace_request_data,
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIsNone(response.parsed)


if __name__ == """__main__""":
    unittest.main()
