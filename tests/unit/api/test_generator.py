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
from unittest.mock import MagicMock, AsyncMock
from http import HTTPStatus
import httpx
import asyncio  # Import asyncio here
import json  # Added import

from hackagent.api.generate.generate_create import sync_detailed, asyncio_detailed
from hackagent.client import AuthenticatedClient
from hackagent.types import Response
from hackagent.models import GenerateRequestRequest
from hackagent.models import GenerateRequestRequestMessagesItem
from hackagent.models import GenerateErrorResponse  # Added import
from hackagent.models import GenerateSuccessResponse  # Added import


class TestGeneratorAPI(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock(spec=AuthenticatedClient)
        self.mock_client.raise_on_unexpected_status = True
        self.mock_httpx_client = MagicMock()
        self.mock_async_httpx_client = MagicMock()
        self.mock_client.get_httpx_client.return_value = self.mock_httpx_client
        self.mock_client.get_async_httpx_client.return_value = (
            self.mock_async_httpx_client
        )

    def test_sync_detailed_success(self):
        success_payload = {"text": "Success"}  # Expected payload
        mock_response = httpx.Response(
            HTTPStatus.OK,
            content=json.dumps(success_payload).encode(),  # JSON content
            headers={"Content-Type": "application/json"},
        )
        # Mock the .json() method directly for sync client
        mock_response.json = MagicMock(return_value=success_payload)
        self.mock_httpx_client.request.return_value = mock_response

        messages_data = [{"role": "user", "content": "Hello"}]
        messages_items = [
            GenerateRequestRequestMessagesItem.from_dict(m) for m in messages_data
        ]
        request_body = GenerateRequestRequest(
            model="test-model", messages=messages_items
        )
        response = sync_detailed(client=self.mock_client, body=request_body)

        self.mock_httpx_client.request.assert_called_once_with(
            method="post",
            url="/api/generate",
            json=request_body.to_dict(),
            data=request_body.to_dict(),
            files=request_body.to_multipart(),
            headers={"Content-Type": "multipart/form-data"},
        )
        self.assertIsInstance(response, Response)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.content, json.dumps(success_payload).encode())
        self.assertIsInstance(response.parsed, GenerateSuccessResponse)
        self.assertEqual(response.parsed.text, success_payload["text"])

    def test_sync_detailed_unexpected_status(self):
        error_payload = {"error": "Error"}  # Expected payload
        mock_response = httpx.Response(
            HTTPStatus.BAD_REQUEST,
            content=json.dumps(error_payload).encode(),  # JSON content
            headers={"Content-Type": "application/json"},
        )
        # Mock the .json() method directly for sync client
        mock_response.json = MagicMock(return_value=error_payload)
        self.mock_httpx_client.request.return_value = mock_response

        messages_data = [{"role": "user", "content": "Hello"}]
        messages_items = [
            GenerateRequestRequestMessagesItem.from_dict(m) for m in messages_data
        ]
        request_body = GenerateRequestRequest(
            model="test-model", messages=messages_items
        )

        response = sync_detailed(client=self.mock_client, body=request_body)

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIsInstance(response.parsed, GenerateErrorResponse)
        self.assertEqual(response.parsed.error, "Error")  # Check parsed error message
        self.mock_httpx_client.request.assert_called_once_with(
            method="post",
            url="/api/generate",
            json=request_body.to_dict(),
            data=request_body.to_dict(),
            files=request_body.to_multipart(),
            headers={"Content-Type": "multipart/form-data"},
        )

    def test_sync_detailed_unexpected_status_no_raise(self):
        self.mock_client.raise_on_unexpected_status = False
        error_payload = {"error": "Error"}  # Expected payload
        mock_response = httpx.Response(
            HTTPStatus.BAD_REQUEST,
            content=json.dumps(error_payload).encode(),  # JSON content
            headers={"Content-Type": "application/json"},
        )
        # Mock the .json() method directly for sync client
        mock_response.json = MagicMock(return_value=error_payload)
        self.mock_httpx_client.request.return_value = mock_response

        messages_data = [{"role": "user", "content": "Hello"}]
        messages_items = [
            GenerateRequestRequestMessagesItem.from_dict(m) for m in messages_data
        ]
        request_body = GenerateRequestRequest(
            model="test-model", messages=messages_items
        )
        response = sync_detailed(client=self.mock_client, body=request_body)

        self.mock_httpx_client.request.assert_called_once_with(
            method="post",
            url="/api/generate",
            json=request_body.to_dict(),
            data=request_body.to_dict(),
            files=request_body.to_multipart(),
            headers={"Content-Type": "multipart/form-data"},
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIsInstance(response.parsed, GenerateErrorResponse)
        self.assertEqual(response.parsed.error, "Error")

    # Note: Using asyncio.run for simplicity here. For more complex async tests,
    # consider unittest.IsolatedAsyncioTestCase or pytest-asyncio.
    def test_asyncio_detailed_success(self):
        success_payload = {"text": "Async Success"}  # Expected payload
        mock_async_response = MagicMock(spec=httpx.Response)
        mock_async_response.status_code = HTTPStatus.OK
        mock_async_response.content = json.dumps(
            success_payload
        ).encode()  # JSON content
        mock_async_response.headers = {"Content-Type": "application/json"}
        mock_async_response.json = MagicMock(
            return_value=success_payload
        )  # Mock .json()

        self.mock_async_httpx_client.request = AsyncMock(
            return_value=mock_async_response
        )

        # Define request_body in the outer scope
        messages_data = [{"role": "user", "content": "Hello"}]
        messages_items = [
            GenerateRequestRequestMessagesItem.from_dict(m) for m in messages_data
        ]
        request_body = GenerateRequestRequest(
            model="test-model", messages=messages_items
        )

        async def run_test():
            # request_body is now accessible here due to closure
            return await asyncio_detailed(client=self.mock_client, body=request_body)

        response = asyncio.run(run_test())

        self.mock_async_httpx_client.request.assert_called_once_with(
            method="post",
            url="/api/generate",
            json=request_body.to_dict(),
            data=request_body.to_dict(),
            files=request_body.to_multipart(),
            headers={"Content-Type": "multipart/form-data"},
        )
        self.assertIsInstance(response, Response)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.content, json.dumps(success_payload).encode())
        self.assertIsInstance(response.parsed, GenerateSuccessResponse)
        self.assertEqual(response.parsed.text, success_payload["text"])

    def test_asyncio_detailed_unexpected_status(self):
        error_payload = {"error": "Async Error"}  # Expected payload
        mock_async_response = MagicMock(spec=httpx.Response)
        mock_async_response.status_code = HTTPStatus.BAD_REQUEST
        mock_async_response.content = json.dumps(error_payload).encode()  # JSON content
        mock_async_response.headers = {"Content-Type": "application/json"}
        mock_async_response.json = MagicMock(return_value=error_payload)  # Mock .json()

        self.mock_async_httpx_client.request = AsyncMock(
            return_value=mock_async_response
        )

        # Define request_body in the outer scope
        messages_data = [{"role": "user", "content": "Hello"}]
        messages_items = [
            GenerateRequestRequestMessagesItem.from_dict(m) for m in messages_data
        ]
        request_body = GenerateRequestRequest(
            model="test-model", messages=messages_items
        )

        async def run_test():
            return await asyncio_detailed(client=self.mock_client, body=request_body)

        response = asyncio.run(run_test())

        self.mock_async_httpx_client.request.assert_called_once_with(
            method="post",
            url="/api/generate",
            json=request_body.to_dict(),
            data=request_body.to_dict(),
            files=request_body.to_multipart(),
            headers={"Content-Type": "multipart/form-data"},
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIsInstance(response.parsed, GenerateErrorResponse)
        self.assertEqual(
            response.parsed.error, "Async Error"
        )  # Check parsed error message

    def test_asyncio_detailed_unexpected_status_no_raise(self):
        self.mock_client.raise_on_unexpected_status = False
        error_payload = {"error": "Async Error"}  # Expected payload
        mock_async_response = MagicMock(spec=httpx.Response)
        mock_async_response.status_code = HTTPStatus.BAD_REQUEST
        mock_async_response.content = json.dumps(error_payload).encode()  # JSON content
        mock_async_response.headers = {"Content-Type": "application/json"}
        mock_async_response.json = MagicMock(return_value=error_payload)  # Mock .json()

        self.mock_async_httpx_client.request = AsyncMock(
            return_value=mock_async_response
        )

        # Define request_body in the outer scope
        messages_data = [{"role": "user", "content": "Hello"}]
        messages_items = [
            GenerateRequestRequestMessagesItem.from_dict(m) for m in messages_data
        ]
        request_body = GenerateRequestRequest(
            model="test-model", messages=messages_items
        )

        async def run_test():
            return await asyncio_detailed(client=self.mock_client, body=request_body)

        response = asyncio.run(run_test())

        self.mock_async_httpx_client.request.assert_called_once_with(
            method="post",
            url="/api/generate",
            json=request_body.to_dict(),
            data=request_body.to_dict(),
            files=request_body.to_multipart(),
            headers={"Content-Type": "multipart/form-data"},
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIsInstance(response.parsed, GenerateErrorResponse)
        self.assertEqual(response.parsed.error, "Async Error")


if __name__ == "__main__":
    unittest.main()
