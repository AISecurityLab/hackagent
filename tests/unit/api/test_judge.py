# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


import asyncio
import json
import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock

import httpx

from hackagent.api.judge.judge_create import asyncio_detailed, sync_detailed
from hackagent.client import AuthenticatedClient
from hackagent.api.models import (
    GenerateErrorResponse,
    GenerateRequestRequest,
    MessageRequest,
    GenerateSuccessResponse,
)
from hackagent.types import Response


class TestJudgeAPI(unittest.TestCase):
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
        success_payload = {
            "id": "test-id-789",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Success"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "text": "Success",
        }
        mock_response = httpx.Response(
            HTTPStatus.OK,
            content=json.dumps(success_payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        mock_response.json = MagicMock(return_value=success_payload)
        self.mock_httpx_client.request.return_value = mock_response

        messages_data = [{"role": "user", "content": "Hello"}]
        messages_items = [MessageRequest.model_validate(m) for m in messages_data]
        request_body = GenerateRequestRequest(
            model="test-model", messages=messages_items
        )
        response = sync_detailed(client=self.mock_client, body=request_body)

        self.mock_httpx_client.request.assert_called_once_with(
            method="post",
            url="/judge",
            json=request_body.model_dump(by_alias=True, mode="json", exclude_none=True),
            data=request_body.model_dump(by_alias=True, mode="json", exclude_none=True),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertIsInstance(response, Response)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.content, json.dumps(success_payload).encode())
        self.assertIsInstance(response.parsed, GenerateSuccessResponse)
        self.assertEqual(response.parsed["text"], success_payload["text"])

    def test_sync_detailed_unexpected_status(self):
        error_payload = {"error": "Error"}
        mock_response = httpx.Response(
            HTTPStatus.BAD_REQUEST,
            content=json.dumps(error_payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        mock_response.json = MagicMock(return_value=error_payload)
        self.mock_httpx_client.request.return_value = mock_response

        messages_data = [{"role": "user", "content": "Hello"}]
        messages_items = [MessageRequest.model_validate(m) for m in messages_data]
        request_body = GenerateRequestRequest(
            model="test-model", messages=messages_items
        )

        response = sync_detailed(client=self.mock_client, body=request_body)

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIsInstance(response.parsed, GenerateErrorResponse)
        self.assertEqual(response.parsed.error, "Error")  # Check parsed error message
        self.mock_httpx_client.request.assert_called_once_with(
            method="post",
            url="/judge",
            json=request_body.model_dump(by_alias=True, mode="json", exclude_none=True),
            data=request_body.model_dump(by_alias=True, mode="json", exclude_none=True),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    def test_sync_detailed_unexpected_status_no_raise(self):
        self.mock_client.raise_on_unexpected_status = False
        error_payload = {"error": "Error"}
        mock_response = httpx.Response(
            HTTPStatus.BAD_REQUEST,
            content=json.dumps(error_payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        mock_response.json = MagicMock(return_value=error_payload)
        self.mock_httpx_client.request.return_value = mock_response

        messages_data = [{"role": "user", "content": "Hello"}]
        messages_items = [MessageRequest.model_validate(m) for m in messages_data]
        request_body = GenerateRequestRequest(
            model="test-model", messages=messages_items
        )
        response = sync_detailed(client=self.mock_client, body=request_body)

        self.mock_httpx_client.request.assert_called_once_with(
            method="post",
            url="/judge",
            json=request_body.model_dump(by_alias=True, mode="json", exclude_none=True),
            data=request_body.model_dump(by_alias=True, mode="json", exclude_none=True),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIsInstance(response.parsed, GenerateErrorResponse)
        self.assertEqual(response.parsed.error, "Error")

    def test_asyncio_detailed_success(self):
        success_payload = {
            "id": "test-id-012",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Async Success"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "text": "Async Success",
        }
        mock_async_response = MagicMock(spec=httpx.Response)
        mock_async_response.status_code = HTTPStatus.OK
        mock_async_response.content = json.dumps(success_payload).encode()
        mock_async_response.headers = {"Content-Type": "application/json"}
        mock_async_response.json = MagicMock(return_value=success_payload)

        self.mock_async_httpx_client.request = AsyncMock(
            return_value=mock_async_response
        )

        # Define request_body in the outer scope
        messages_data = [{"role": "user", "content": "Hello"}]
        messages_items = [MessageRequest.model_validate(m) for m in messages_data]
        request_body = GenerateRequestRequest(
            model="test-model", messages=messages_items
        )

        async def run_test():
            return await asyncio_detailed(client=self.mock_client, body=request_body)

        response = asyncio.run(run_test())

        self.mock_async_httpx_client.request.assert_called_once_with(
            method="post",
            url="/judge",
            json=request_body.model_dump(by_alias=True, mode="json", exclude_none=True),
            data=request_body.model_dump(by_alias=True, mode="json", exclude_none=True),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertIsInstance(response, Response)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.content, json.dumps(success_payload).encode())
        self.assertIsInstance(response.parsed, GenerateSuccessResponse)
        self.assertEqual(response.parsed["text"], success_payload["text"])

    def test_asyncio_detailed_unexpected_status(self):
        error_payload = {"error": "Async Error"}
        mock_async_response = MagicMock(spec=httpx.Response)
        mock_async_response.status_code = HTTPStatus.BAD_REQUEST
        mock_async_response.content = json.dumps(error_payload).encode()
        mock_async_response.headers = {"Content-Type": "application/json"}
        mock_async_response.json = MagicMock(return_value=error_payload)

        self.mock_async_httpx_client.request = AsyncMock(
            return_value=mock_async_response
        )

        # Define request_body in the outer scope
        messages_data = [{"role": "user", "content": "Hello"}]
        messages_items = [MessageRequest.model_validate(m) for m in messages_data]
        request_body = GenerateRequestRequest(
            model="test-model", messages=messages_items
        )

        async def run_test():
            return await asyncio_detailed(client=self.mock_client, body=request_body)

        response = asyncio.run(run_test())

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIsInstance(response.parsed, GenerateErrorResponse)
        self.assertEqual(
            response.parsed.error, "Async Error"
        )  # Check parsed error message
        self.mock_async_httpx_client.request.assert_called_once_with(
            method="post",
            url="/judge",
            json=request_body.model_dump(by_alias=True, mode="json", exclude_none=True),
            data=request_body.model_dump(by_alias=True, mode="json", exclude_none=True),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    def test_asyncio_detailed_unexpected_status_no_raise(self):
        self.mock_client.raise_on_unexpected_status = False
        error_payload = {"error": "Async Error"}
        mock_async_response = MagicMock(spec=httpx.Response)
        mock_async_response.status_code = HTTPStatus.BAD_REQUEST
        mock_async_response.content = json.dumps(error_payload).encode()
        mock_async_response.headers = {"Content-Type": "application/json"}
        mock_async_response.json = MagicMock(return_value=error_payload)

        self.mock_async_httpx_client.request = AsyncMock(
            return_value=mock_async_response
        )

        # Define request_body in the outer scope
        messages_data = [{"role": "user", "content": "Hello"}]
        messages_items = [MessageRequest.model_validate(m) for m in messages_data]
        request_body = GenerateRequestRequest(
            model="test-model", messages=messages_items
        )

        async def run_test():
            return await asyncio_detailed(client=self.mock_client, body=request_body)

        response = asyncio.run(run_test())

        self.mock_async_httpx_client.request.assert_called_once_with(
            method="post",
            url="/judge",
            json=request_body.model_dump(by_alias=True, mode="json", exclude_none=True),
            data=request_body.model_dump(by_alias=True, mode="json", exclude_none=True),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIsInstance(response.parsed, GenerateErrorResponse)
        self.assertEqual(response.parsed.error, "Async Error")


if __name__ == "__main__":
    unittest.main()
