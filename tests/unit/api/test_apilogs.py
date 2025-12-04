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

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import Response

from hackagent.api.apilogs import apilogs_list, apilogs_retrieve
from hackagent.client import AuthenticatedClient
from hackagent.errors import UnexpectedStatus
from hackagent.models.api_token_log import APITokenLog
from hackagent.models.paginated_api_token_log_list import PaginatedAPITokenLogList


@pytest.fixture
def authenticated_client() -> AuthenticatedClient:
    return AuthenticatedClient(base_url="http://localhost:8000", token="test_token")


def test_get_kwargs(authenticated_client: AuthenticatedClient):
    kwargs = apilogs_list._get_kwargs(page=1)
    assert kwargs["method"] == "get"
    assert kwargs["url"] == "/apilogs"
    assert kwargs["params"]["page"] == 1

    kwargs_no_page = apilogs_list._get_kwargs()
    assert "page" not in kwargs_no_page["params"]


def test_sync_detailed_success(authenticated_client: AuthenticatedClient):
    mock_response_data = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": "test_id_sync_list",
                "timestamp": "2024-01-01T00:00:00Z",
                "api_key_prefix": "sync_list_pref",
                "user_username": "sync_list_user",
                "organization_name": "sync_list_org",
                "model_id_used": "gpt-4-sync-list",
                "api_endpoint": "generator_sync_list",
                "input_tokens": 10,
                "output_tokens": 20,
                "credits_deducted": "0.001",
                "request_payload_preview": "Request sync list",
                "response_payload_preview": "Response sync list",
            }
        ],
    }
    mock_response = Response(200, json=mock_response_data)

    with patch.object(
        authenticated_client.get_httpx_client(), "request", return_value=mock_response
    ) as mock_request:
        response = apilogs_list.sync_detailed(client=authenticated_client, page=1)

    mock_request.assert_called_once_with(
        method="get", url="/apilogs", params={"page": 1}
    )
    assert response.status_code == 200
    assert isinstance(response.parsed, PaginatedAPITokenLogList)
    assert response.parsed.count == 1
    assert response.parsed.results[0].id == "test_id_sync_list"


def test_sync_detailed_unexpected_status(authenticated_client: AuthenticatedClient):
    mock_response = Response(500, content=b"Internal Server Error")
    authenticated_client.raise_on_unexpected_status = True

    with patch.object(
        authenticated_client.get_httpx_client(), "request", return_value=mock_response
    ) as mock_request:
        with pytest.raises(UnexpectedStatus) as excinfo:
            apilogs_list.sync_detailed(client=authenticated_client, page=1)

    mock_request.assert_called_once_with(
        method="get", url="/apilogs", params={"page": 1}
    )
    assert excinfo.value.status_code == 500
    assert excinfo.value.content == b"Internal Server Error"


def test_sync_detailed_no_raise_unexpected_status(
    authenticated_client: AuthenticatedClient,
):
    mock_response = Response(500, content=b"Internal Server Error")
    authenticated_client.raise_on_unexpected_status = False

    with patch.object(
        authenticated_client.get_httpx_client(), "request", return_value=mock_response
    ) as mock_request:
        response = apilogs_list.sync_detailed(client=authenticated_client, page=1)

    mock_request.assert_called_once_with(
        method="get", url="/apilogs", params={"page": 1}
    )
    assert response.status_code == 500
    assert response.parsed is None


def test_sync_success(authenticated_client: AuthenticatedClient):
    mock_parsed_response = MagicMock(spec=PaginatedAPITokenLogList)
    mock_detailed_response = MagicMock()
    mock_detailed_response.parsed = mock_parsed_response

    with patch(
        "hackagent.api.apilogs.apilogs_list.sync_detailed",
        return_value=mock_detailed_response,
    ) as mock_sync_detailed:
        parsed = apilogs_list.sync(client=authenticated_client, page=1)

    mock_sync_detailed.assert_called_once_with(client=authenticated_client, page=1)
    assert parsed == mock_parsed_response


@pytest.mark.asyncio
async def test_asyncio_detailed_success(authenticated_client: AuthenticatedClient):
    mock_response_data = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": "test_id_async_list",
                "timestamp": "2024-01-01T00:02:00Z",
                "api_key_prefix": "async_list_pref",
                "user_username": "async_list_user",
                "organization_name": "async_list_org",
                "model_id_used": "gpt-3.5-turbo-async-list",
                "api_endpoint": "apilogs_list_endpoint_async",
                "input_tokens": 15,
                "output_tokens": 25,
                "credits_deducted": "0.0015",
                "request_payload_preview": "Async list request new",
                "response_payload_preview": "Async list response new",
            }
        ],
    }
    mock_http_response = Response(200, json=mock_response_data)
    mock_async_httpx_client = AsyncMock()
    mock_async_httpx_client.request = AsyncMock(return_value=mock_http_response)

    with patch.object(
        AuthenticatedClient,
        "get_async_httpx_client",
        autospec=True,
        return_value=mock_async_httpx_client,
    ) as mock_get_client_method:
        response = await apilogs_list.asyncio_detailed(
            client=authenticated_client, page=1
        )

    mock_get_client_method.assert_called_once_with(authenticated_client)
    mock_async_httpx_client.request.assert_called_once_with(
        method="get", url="/apilogs", params={"page": 1}
    )
    assert response.status_code == 200
    assert isinstance(response.parsed, PaginatedAPITokenLogList)
    assert response.parsed.count == 1
    assert response.parsed.results[0].id == "test_id_async_list"


@pytest.mark.asyncio
async def test_asyncio_detailed_unexpected_status(
    authenticated_client: AuthenticatedClient,
):
    mock_http_response = Response(500, content=b"Internal Server Error")
    authenticated_client.raise_on_unexpected_status = True
    mock_async_httpx_client = AsyncMock()
    mock_async_httpx_client.request = AsyncMock(return_value=mock_http_response)

    with patch.object(
        AuthenticatedClient,
        "get_async_httpx_client",
        autospec=True,
        return_value=mock_async_httpx_client,
    ) as mock_get_client_method:
        with pytest.raises(UnexpectedStatus) as excinfo:
            await apilogs_list.asyncio_detailed(client=authenticated_client, page=1)

    mock_get_client_method.assert_called_once_with(authenticated_client)
    mock_async_httpx_client.request.assert_called_once_with(
        method="get", url="/apilogs", params={"page": 1}
    )
    assert excinfo.value.status_code == 500
    assert excinfo.value.content == b"Internal Server Error"


@pytest.mark.asyncio
async def test_asyncio_detailed_no_raise_unexpected_status(
    authenticated_client: AuthenticatedClient,
):
    mock_http_response = Response(500, content=b"Internal Server Error")
    authenticated_client.raise_on_unexpected_status = False
    mock_async_httpx_client = AsyncMock()
    mock_async_httpx_client.request = AsyncMock(return_value=mock_http_response)

    with patch.object(
        AuthenticatedClient,
        "get_async_httpx_client",
        autospec=True,
        return_value=mock_async_httpx_client,
    ) as mock_get_client_method:
        response = await apilogs_list.asyncio_detailed(
            client=authenticated_client, page=1
        )

    mock_get_client_method.assert_called_once_with(authenticated_client)
    mock_async_httpx_client.request.assert_called_once_with(
        method="get", url="/apilogs", params={"page": 1}
    )
    assert response.status_code == 500
    assert response.parsed is None


@pytest.mark.asyncio
async def test_asyncio_success(authenticated_client: AuthenticatedClient):
    mock_parsed_response = MagicMock(spec=PaginatedAPITokenLogList)
    mock_detailed_response = MagicMock()
    mock_detailed_response.parsed = mock_parsed_response

    # Need to mock the awaitable
    async def mock_asyncio_detailed(*args, **kwargs):
        return mock_detailed_response

    with patch(
        "hackagent.api.apilogs.apilogs_list.asyncio_detailed", new=mock_asyncio_detailed
    ) as _:
        parsed = await apilogs_list.asyncio(client=authenticated_client, page=1)

    # mock_async_detailed_patch.assert_called_once_with(client=authenticated_client, page=1)
    assert parsed == mock_parsed_response


# Tests for apilogs_retrieve


def test_retrieve_get_kwargs():
    kwargs = apilogs_retrieve._get_kwargs(id=123)
    assert kwargs["method"] == "get"
    assert kwargs["url"] == "/apilogs/123"


def test_retrieve_sync_detailed_success(authenticated_client: AuthenticatedClient):
    mock_response_data = {
        "id": "test_log_id_sync_retrieve",
        "timestamp": "2024-01-01T00:01:00Z",
        "api_key_prefix": "sync_retrieve_pref",
        "user_username": "sync_retrieve_user",
        "organization_name": "sync_retrieve_org",
        "model_id_used": "gemini-pro-sync-retrieve",
        "api_endpoint": "agent_sync_retrieve",
        "input_tokens": 12,
        "output_tokens": 22,
        "credits_deducted": "0.0012",
        "request_payload_preview": "Sync retrieve request new",
        "response_payload_preview": "Sync retrieve response new",
    }
    mock_response = Response(200, json=mock_response_data)

    with patch.object(
        authenticated_client.get_httpx_client(), "request", return_value=mock_response
    ) as mock_request:
        response = apilogs_retrieve.sync_detailed(client=authenticated_client, id=123)

    mock_request.assert_called_once_with(method="get", url="/apilogs/123")
    assert response.status_code == 200
    assert isinstance(response.parsed, APITokenLog)
    assert response.parsed.id == "test_log_id_sync_retrieve"


def test_retrieve_sync_detailed_unexpected_status(
    authenticated_client: AuthenticatedClient,
):
    mock_response = Response(404, content=b"Not Found")
    authenticated_client.raise_on_unexpected_status = True

    with patch.object(
        authenticated_client.get_httpx_client(), "request", return_value=mock_response
    ) as mock_request:
        with pytest.raises(UnexpectedStatus) as excinfo:
            apilogs_retrieve.sync_detailed(client=authenticated_client, id=123)

    mock_request.assert_called_once_with(method="get", url="/apilogs/123")
    assert excinfo.value.status_code == 404
    assert excinfo.value.content == b"Not Found"


def test_retrieve_sync_detailed_no_raise_unexpected_status(
    authenticated_client: AuthenticatedClient,
):
    mock_response = Response(404, content=b"Not Found")
    authenticated_client.raise_on_unexpected_status = False

    with patch.object(
        authenticated_client.get_httpx_client(), "request", return_value=mock_response
    ) as mock_request:
        response = apilogs_retrieve.sync_detailed(client=authenticated_client, id=123)

    mock_request.assert_called_once_with(method="get", url="/apilogs/123")
    assert response.status_code == 404
    assert response.parsed is None


def test_retrieve_sync_success(authenticated_client: AuthenticatedClient):
    mock_parsed_response = MagicMock(spec=APITokenLog)
    mock_detailed_response = MagicMock()
    mock_detailed_response.parsed = mock_parsed_response

    with patch(
        "hackagent.api.apilogs.apilogs_retrieve.sync_detailed",
        return_value=mock_detailed_response,
    ) as mock_sync_detailed:
        parsed = apilogs_retrieve.sync(client=authenticated_client, id=123)

    mock_sync_detailed.assert_called_once_with(client=authenticated_client, id=123)
    assert parsed == mock_parsed_response


@pytest.mark.asyncio
async def test_retrieve_asyncio_detailed_success(
    authenticated_client: AuthenticatedClient,
):
    mock_response_data = {
        "id": "test_log_id_async_retrieve",
        "timestamp": "2024-01-01T00:03:00Z",
        "api_key_prefix": "async_retrieve_pref",
        "user_username": "async_retrieve_user",
        "organization_name": "async_retrieve_org",
        "model_id_used": "command-r-async-retrieve",
        "api_endpoint": "apilogs_retrieve_endpoint_async",
        "input_tokens": 8,
        "output_tokens": 18,
        "credits_deducted": "0.0008",
        "request_payload_preview": "Async retrieve request new",
        "response_payload_preview": "Async retrieve response new",
    }
    mock_http_response = Response(200, json=mock_response_data)
    mock_async_httpx_client = AsyncMock()
    mock_async_httpx_client.request = AsyncMock(return_value=mock_http_response)

    with patch.object(
        AuthenticatedClient,
        "get_async_httpx_client",
        autospec=True,
        return_value=mock_async_httpx_client,
    ) as mock_get_client_method:
        response = await apilogs_retrieve.asyncio_detailed(
            client=authenticated_client, id=123
        )

    mock_get_client_method.assert_called_once_with(authenticated_client)
    mock_async_httpx_client.request.assert_called_once_with(
        method="get", url="/apilogs/123"
    )
    assert response.status_code == 200
    assert isinstance(response.parsed, APITokenLog)
    assert response.parsed.id == "test_log_id_async_retrieve"


@pytest.mark.asyncio
async def test_retrieve_asyncio_detailed_unexpected_status(
    authenticated_client: AuthenticatedClient,
):
    mock_http_response = Response(401, content=b"Unauthorized")
    authenticated_client.raise_on_unexpected_status = True
    mock_async_httpx_client = AsyncMock()
    mock_async_httpx_client.request = AsyncMock(return_value=mock_http_response)

    with patch.object(
        AuthenticatedClient,
        "get_async_httpx_client",
        autospec=True,
        return_value=mock_async_httpx_client,
    ) as mock_get_client_method:
        with pytest.raises(UnexpectedStatus) as excinfo:
            await apilogs_retrieve.asyncio_detailed(client=authenticated_client, id=123)

    mock_get_client_method.assert_called_once_with(authenticated_client)
    mock_async_httpx_client.request.assert_called_once_with(
        method="get", url="/apilogs/123"
    )
    assert excinfo.value.status_code == 401
    assert excinfo.value.content == b"Unauthorized"


@pytest.mark.asyncio
async def test_retrieve_asyncio_detailed_no_raise_unexpected_status(
    authenticated_client: AuthenticatedClient,
):
    mock_http_response = Response(403, content=b"Forbidden")
    authenticated_client.raise_on_unexpected_status = False
    mock_async_httpx_client = AsyncMock()
    mock_async_httpx_client.request = AsyncMock(return_value=mock_http_response)

    with patch.object(
        AuthenticatedClient,
        "get_async_httpx_client",
        autospec=True,
        return_value=mock_async_httpx_client,
    ) as mock_get_client_method:
        response = await apilogs_retrieve.asyncio_detailed(
            client=authenticated_client, id=123
        )

    mock_get_client_method.assert_called_once_with(authenticated_client)
    mock_async_httpx_client.request.assert_called_once_with(
        method="get", url="/apilogs/123"
    )
    assert response.status_code == 403
    assert response.parsed is None


@pytest.mark.asyncio
async def test_retrieve_asyncio_success(authenticated_client: AuthenticatedClient):
    mock_parsed_response = MagicMock(spec=APITokenLog)
    mock_detailed_response = MagicMock()
    mock_detailed_response.parsed = mock_parsed_response

    # Need to mock the awaitable
    async def mock_asyncio_detailed(*args, **kwargs):
        return mock_detailed_response

    with patch(
        "hackagent.api.apilogs.apilogs_retrieve.asyncio_detailed",
        new=mock_asyncio_detailed,
    ) as _:
        parsed = await apilogs_retrieve.asyncio(client=authenticated_client, id=123)

    # mock_async_detailed_patch.assert_called_once_with(client=authenticated_client, id=123)
    assert parsed == mock_parsed_response
