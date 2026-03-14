from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import Response
from ..models import Run, RunRequest


def _get_kwargs(
    id: UUID,
    *,
    body: RunRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "put",
        "url": "/run/{id}".format(
            id=quote(str(id), safe=""),
        ),
    }

    _kwargs["json"] = body.model_dump(by_alias=True, mode="json", exclude_none=True)

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Run | None:
    if response.status_code == 200:
        response_200 = Run.model_validate(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Run]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    id: UUID,
    *,
    client: AuthenticatedClient,
    body: RunRequest,
) -> Response[Run]:
    """ViewSet for managing Run instances.
    Primarily for listing/retrieving runs.
    Creation of server-side runs is handled by custom actions.
    Runs initiated from Attack definitions are created via AttackViewSet.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Auth0 authentication is supported as fallback for web dashboard use.
    This is a core SDK operation for executing and monitoring security tests.

    Args:
        id (UUID):
        body (RunRequest): Serializer for the Run model, used for both input and output.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Run]
    """

    kwargs = _get_kwargs(
        id=id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    id: UUID,
    *,
    client: AuthenticatedClient,
    body: RunRequest,
) -> Run | None:
    """ViewSet for managing Run instances.
    Primarily for listing/retrieving runs.
    Creation of server-side runs is handled by custom actions.
    Runs initiated from Attack definitions are created via AttackViewSet.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Auth0 authentication is supported as fallback for web dashboard use.
    This is a core SDK operation for executing and monitoring security tests.

    Args:
        id (UUID):
        body (RunRequest): Serializer for the Run model, used for both input and output.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Run
    """

    return sync_detailed(
        id=id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    id: UUID,
    *,
    client: AuthenticatedClient,
    body: RunRequest,
) -> Response[Run]:
    """ViewSet for managing Run instances.
    Primarily for listing/retrieving runs.
    Creation of server-side runs is handled by custom actions.
    Runs initiated from Attack definitions are created via AttackViewSet.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Auth0 authentication is supported as fallback for web dashboard use.
    This is a core SDK operation for executing and monitoring security tests.

    Args:
        id (UUID):
        body (RunRequest): Serializer for the Run model, used for both input and output.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Run]
    """

    kwargs = _get_kwargs(
        id=id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    id: UUID,
    *,
    client: AuthenticatedClient,
    body: RunRequest,
) -> Run | None:
    """ViewSet for managing Run instances.
    Primarily for listing/retrieving runs.
    Creation of server-side runs is handled by custom actions.
    Runs initiated from Attack definitions are created via AttackViewSet.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Auth0 authentication is supported as fallback for web dashboard use.
    This is a core SDK operation for executing and monitoring security tests.

    Args:
        id (UUID):
        body (RunRequest): Serializer for the Run model, used for both input and output.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Run
    """

    return (
        await asyncio_detailed(
            id=id,
            client=client,
            body=body,
        )
    ).parsed
