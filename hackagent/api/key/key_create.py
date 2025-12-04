from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.user_api_key import UserAPIKey
from ...models.user_api_key_request import UserAPIKeyRequest
from ...types import Response


def _get_kwargs(
    *,
    body: UserAPIKeyRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/key",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[UserAPIKey]:
    if response.status_code == 201:
        response_201 = UserAPIKey.from_dict(response.json())

        return response_201
    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[UserAPIKey]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: UserAPIKeyRequest,
) -> Response[UserAPIKey]:
    """ViewSet for managing User API Keys.

    Web-only endpoint - requires Auth0 authentication.
    API keys cannot manage other API keys for security reasons.

    Args:
        body (UserAPIKeyRequest): Serializer for User API Keys.
            Exposes read-only information about the key, including its prefix.
            The full key is only shown once upon creation by the ViewSet.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[UserAPIKey]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    body: UserAPIKeyRequest,
) -> Optional[UserAPIKey]:
    """ViewSet for managing User API Keys.

    Web-only endpoint - requires Auth0 authentication.
    API keys cannot manage other API keys for security reasons.

    Args:
        body (UserAPIKeyRequest): Serializer for User API Keys.
            Exposes read-only information about the key, including its prefix.
            The full key is only shown once upon creation by the ViewSet.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        UserAPIKey
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: UserAPIKeyRequest,
) -> Response[UserAPIKey]:
    """ViewSet for managing User API Keys.

    Web-only endpoint - requires Auth0 authentication.
    API keys cannot manage other API keys for security reasons.

    Args:
        body (UserAPIKeyRequest): Serializer for User API Keys.
            Exposes read-only information about the key, including its prefix.
            The full key is only shown once upon creation by the ViewSet.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[UserAPIKey]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: UserAPIKeyRequest,
) -> Optional[UserAPIKey]:
    """ViewSet for managing User API Keys.

    Web-only endpoint - requires Auth0 authentication.
    API keys cannot manage other API keys for security reasons.

    Args:
        body (UserAPIKeyRequest): Serializer for User API Keys.
            Exposes read-only information about the key, including its prefix.
            The full key is only shown once upon creation by the ViewSet.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        UserAPIKey
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
