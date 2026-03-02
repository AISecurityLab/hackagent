# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import Response

from hackagent.api.checkout import checkout_create
from hackagent.client import AuthenticatedClient
from hackagent.errors import UnexpectedStatus
from hackagent.api.models import (
    CheckoutSessionRequestRequest,
)
from hackagent.api.models import CheckoutSessionResponse
from hackagent.api.models import GenericErrorResponse


@pytest.fixture
def authenticated_client() -> AuthenticatedClient:
    return AuthenticatedClient(base_url="http://localhost:8000", token="test_token")


@pytest.fixture
def checkout_request_body() -> CheckoutSessionRequestRequest:
    body = CheckoutSessionRequestRequest(credits_to_purchase=100)
    body.additional_properties["price_id"] = "price_123"
    body.additional_properties["success_url"] = "http://success.com"
    body.additional_properties["cancel_url"] = "http://cancel.com"
    return body


def test_get_kwargs(checkout_request_body: CheckoutSessionRequestRequest):
    kwargs = checkout_create._get_kwargs(body=checkout_request_body)
    assert kwargs["method"] == "post"
    assert kwargs["url"] == "/checkout/"
    # After Pydantic migration the body is sent as JSON or form-encoded data
    assert "data" in kwargs or "json" in kwargs

    different_body = CheckoutSessionRequestRequest(credits_to_purchase=50)
    kwargs_different = checkout_create._get_kwargs(body=different_body)
    assert kwargs_different["method"] == "post"


def test_parse_response_success(authenticated_client: AuthenticatedClient):
    mock_response_data = {"checkout_url": "http://stripe.com/checkout/sess_123"}
    http_response = Response(200, json=mock_response_data)
    parsed = checkout_create._parse_response(
        client=authenticated_client, response=http_response
    )
    assert isinstance(parsed, CheckoutSessionResponse)
    assert str(parsed.checkout_url) == "http://stripe.com/checkout/sess_123"


@pytest.mark.parametrize(
    "status_code, error_message",
    [
        (400, "Bad Request Error"),
        (404, "Not Found Error"),
        (500, "Internal Server Error Message"),
    ],
)
def test_parse_response_error(
    authenticated_client: AuthenticatedClient, status_code: int, error_message: str
):
    mock_response_data = {
        "error": error_message,
        "details": "More details about the error",
    }
    http_response = Response(status_code, json=mock_response_data)
    parsed = checkout_create._parse_response(
        client=authenticated_client, response=http_response
    )
    assert isinstance(parsed, GenericErrorResponse)
    assert parsed.error == error_message
    assert parsed.details == "More details about the error"


def test_parse_response_unexpected_status_raise(
    authenticated_client: AuthenticatedClient,
):
    http_response = Response(503, content=b"Service Unavailable")
    authenticated_client.raise_on_unexpected_status = True
    with pytest.raises(UnexpectedStatus) as excinfo:
        checkout_create._parse_response(
            client=authenticated_client, response=http_response
        )
    assert excinfo.value.status_code == 503
    assert excinfo.value.content == b"Service Unavailable"


def test_parse_response_unexpected_status_no_raise(
    authenticated_client: AuthenticatedClient,
):
    http_response = Response(503, content=b"Service Unavailable")
    authenticated_client.raise_on_unexpected_status = False
    parsed = checkout_create._parse_response(
        client=authenticated_client, response=http_response
    )
    assert parsed is None


def test_sync_detailed_success(
    authenticated_client: AuthenticatedClient,
    checkout_request_body: CheckoutSessionRequestRequest,
):
    mock_response_data = {"checkout_url": "http://stripe.com/checkout/sess_abc"}
    mock_http_response = Response(200, json=mock_response_data)

    with patch.object(
        authenticated_client.get_httpx_client(),
        "request",
        return_value=mock_http_response,
    ) as mock_request:
        response = checkout_create.sync_detailed(
            client=authenticated_client, body=checkout_request_body
        )

    expected_kwargs = checkout_create._get_kwargs(body=checkout_request_body)
    mock_request.assert_called_once_with(**expected_kwargs)
    assert response.status_code == 200
    assert isinstance(response.parsed, CheckoutSessionResponse)
    assert str(response.parsed.checkout_url) == "http://stripe.com/checkout/sess_abc"


@pytest.mark.parametrize("status_code", [400, 404, 500])
def test_sync_detailed_error_responses(
    authenticated_client: AuthenticatedClient,
    checkout_request_body: CheckoutSessionRequestRequest,
    status_code: int,
):
    mock_response_data = {
        "error": "Sync Error Occurred",
        "details": "Sync error details",
    }
    mock_http_response = Response(status_code, json=mock_response_data)

    with patch.object(
        authenticated_client.get_httpx_client(),
        "request",
        return_value=mock_http_response,
    ) as mock_request:
        response = checkout_create.sync_detailed(
            client=authenticated_client, body=checkout_request_body
        )

    expected_kwargs = checkout_create._get_kwargs(body=checkout_request_body)
    mock_request.assert_called_once_with(**expected_kwargs)
    assert response.status_code == status_code
    assert isinstance(response.parsed, GenericErrorResponse)
    assert response.parsed.error == "Sync Error Occurred"


def test_sync_success(
    authenticated_client: AuthenticatedClient,
    checkout_request_body: CheckoutSessionRequestRequest,
):
    mock_parsed_response = MagicMock(spec=CheckoutSessionResponse)
    mock_detailed_response = MagicMock()
    mock_detailed_response.parsed = mock_parsed_response

    with patch(
        "hackagent.api.checkout.checkout_create.sync_detailed",
        return_value=mock_detailed_response,
    ) as mock_sync_detailed:
        parsed = checkout_create.sync(
            client=authenticated_client, body=checkout_request_body
        )

    mock_sync_detailed.assert_called_once_with(
        client=authenticated_client, body=checkout_request_body
    )
    assert parsed == mock_parsed_response


@pytest.mark.asyncio
async def test_asyncio_detailed_success(
    authenticated_client: AuthenticatedClient,
    checkout_request_body: CheckoutSessionRequestRequest,
):
    mock_response_data = {"checkout_url": "http://stripe.com/checkout/sess_def"}
    mock_http_response = Response(200, json=mock_response_data)
    mock_async_httpx_client = AsyncMock()
    mock_async_httpx_client.request = AsyncMock(return_value=mock_http_response)

    with patch.object(
        AuthenticatedClient,
        "get_async_httpx_client",
        autospec=True,
        return_value=mock_async_httpx_client,
    ) as mock_get_client_method:
        response = await checkout_create.asyncio_detailed(
            client=authenticated_client, body=checkout_request_body
        )

    expected_kwargs = checkout_create._get_kwargs(body=checkout_request_body)
    mock_get_client_method.assert_called_once_with(authenticated_client)
    mock_async_httpx_client.request.assert_called_once_with(**expected_kwargs)
    assert response.status_code == 200
    assert isinstance(response.parsed, CheckoutSessionResponse)
    assert str(response.parsed.checkout_url) == "http://stripe.com/checkout/sess_def"


@pytest.mark.parametrize("status_code", [400, 404, 500])
@pytest.mark.asyncio
async def test_asyncio_detailed_error_responses(
    authenticated_client: AuthenticatedClient,
    checkout_request_body: CheckoutSessionRequestRequest,
    status_code: int,
):
    mock_response_data = {
        "error": "Async Detailed Error",
        "details": "Async detailed error details",
    }
    mock_http_response = Response(status_code, json=mock_response_data)
    mock_async_httpx_client = AsyncMock()
    mock_async_httpx_client.request = AsyncMock(return_value=mock_http_response)

    with patch.object(
        AuthenticatedClient,
        "get_async_httpx_client",
        autospec=True,
        return_value=mock_async_httpx_client,
    ) as mock_get_client_method:
        response = await checkout_create.asyncio_detailed(
            client=authenticated_client, body=checkout_request_body
        )

    expected_kwargs = checkout_create._get_kwargs(body=checkout_request_body)
    mock_get_client_method.assert_called_once_with(authenticated_client)
    mock_async_httpx_client.request.assert_called_once_with(**expected_kwargs)
    assert response.status_code == status_code
    assert isinstance(response.parsed, GenericErrorResponse)
    assert response.parsed.error == "Async Detailed Error"


@pytest.mark.asyncio
async def test_asyncio_success(
    authenticated_client: AuthenticatedClient,
    checkout_request_body: CheckoutSessionRequestRequest,
):
    mock_parsed_response = MagicMock(spec=CheckoutSessionResponse)
    mock_detailed_response = MagicMock()
    mock_detailed_response.parsed = mock_parsed_response

    async def mock_asyncio_detailed(*args, **kwargs):
        return mock_detailed_response

    with patch(
        "hackagent.api.checkout.checkout_create.asyncio_detailed",
        new=mock_asyncio_detailed,
    ) as _:
        parsed = await checkout_create.asyncio(
            client=authenticated_client, body=checkout_request_body
        )

    assert parsed == mock_parsed_response
