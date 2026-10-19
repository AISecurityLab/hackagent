from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ..models import KeyContextRetrieveResponse200
from ...types import Response


def _get_kwargs() -> dict[str, Any]:
    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/key/context",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> KeyContextRetrieveResponse200 | None:
    if response.status_code == 200:
        response_200 = KeyContextRetrieveResponse200.model_validate(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[KeyContextRetrieveResponse200]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
) -> Response[KeyContextRetrieveResponse200]:
    """Caller identity context

     Returns the caller's user ID, username, and organization details. Accessible with both API Key and
    Auth0 bearer tokens. The SDK uses this endpoint to bootstrap organization context without needing to
    page through the agent list.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[KeyContextRetrieveResponse200]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
) -> KeyContextRetrieveResponse200 | None:
    """Caller identity context

     Returns the caller's user ID, username, and organization details. Accessible with both API Key and
    Auth0 bearer tokens. The SDK uses this endpoint to bootstrap organization context without needing to
    page through the agent list.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        KeyContextRetrieveResponse200
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
) -> Response[KeyContextRetrieveResponse200]:
    """Caller identity context

     Returns the caller's user ID, username, and organization details. Accessible with both API Key and
    Auth0 bearer tokens. The SDK uses this endpoint to bootstrap organization context without needing to
    page through the agent list.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[KeyContextRetrieveResponse200]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
) -> KeyContextRetrieveResponse200 | None:
    """Caller identity context

     Returns the caller's user ID, username, and organization details. Accessible with both API Key and
    Auth0 bearer tokens. The SDK uses this endpoint to bootstrap organization context without needing to
    page through the agent list.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        KeyContextRetrieveResponse200
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
