from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import Response
from ..models import UserAPIKey


def _get_kwargs(
    prefix: str,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/key/{prefix}".format(
            prefix=quote(str(prefix), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> UserAPIKey | None:
    if response.status_code == 200:
        response_200 = UserAPIKey.model_validate(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[UserAPIKey]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    prefix: str,
    *,
    client: AuthenticatedClient,
) -> Response[UserAPIKey]:
    """ViewSet for managing User API Keys.

    Web-only endpoint - requires Auth0 authentication.
    API keys cannot manage other API keys for security reasons.

    Args:
        prefix (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[UserAPIKey]
    """

    kwargs = _get_kwargs(
        prefix=prefix,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    prefix: str,
    *,
    client: AuthenticatedClient,
) -> UserAPIKey | None:
    """ViewSet for managing User API Keys.

    Web-only endpoint - requires Auth0 authentication.
    API keys cannot manage other API keys for security reasons.

    Args:
        prefix (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        UserAPIKey
    """

    return sync_detailed(
        prefix=prefix,
        client=client,
    ).parsed


async def asyncio_detailed(
    prefix: str,
    *,
    client: AuthenticatedClient,
) -> Response[UserAPIKey]:
    """ViewSet for managing User API Keys.

    Web-only endpoint - requires Auth0 authentication.
    API keys cannot manage other API keys for security reasons.

    Args:
        prefix (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[UserAPIKey]
    """

    kwargs = _get_kwargs(
        prefix=prefix,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    prefix: str,
    *,
    client: AuthenticatedClient,
) -> UserAPIKey | None:
    """ViewSet for managing User API Keys.

    Web-only endpoint - requires Auth0 authentication.
    API keys cannot manage other API keys for security reasons.

    Args:
        prefix (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        UserAPIKey
    """

    return (
        await asyncio_detailed(
            prefix=prefix,
            client=client,
        )
    ).parsed
