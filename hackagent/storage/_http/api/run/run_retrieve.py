from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import UNSET, Response, Unset
from ..models import Run


def _get_kwargs(
    id: UUID,
    *,
    include_results: bool | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["include_results"] = include_results

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/run/{id}".format(
            id=quote(str(id), safe=""),
        ),
        "params": params,
    }

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
    include_results: bool | Unset = UNSET,
) -> Response[Run]:
    """ViewSet for listing, retrieving, annotating and deleting runs.
    Runs are created only by a campaign launch (POST /campaign/{id}/launch)
    and by the executor protocol, never through this endpoint.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Login token (Auth0 or Keycloak) authentication is supported for web dashboard use.
    This is a core SDK operation for executing and monitoring security tests.

    Args:
        id (UUID):
        include_results (bool | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Run]
    """

    kwargs = _get_kwargs(
        id=id,
        include_results=include_results,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    id: UUID,
    *,
    client: AuthenticatedClient,
    include_results: bool | Unset = UNSET,
) -> Run | None:
    """ViewSet for listing, retrieving, annotating and deleting runs.
    Runs are created only by a campaign launch (POST /campaign/{id}/launch)
    and by the executor protocol, never through this endpoint.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Login token (Auth0 or Keycloak) authentication is supported for web dashboard use.
    This is a core SDK operation for executing and monitoring security tests.

    Args:
        id (UUID):
        include_results (bool | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Run
    """

    return sync_detailed(
        id=id,
        client=client,
        include_results=include_results,
    ).parsed


async def asyncio_detailed(
    id: UUID,
    *,
    client: AuthenticatedClient,
    include_results: bool | Unset = UNSET,
) -> Response[Run]:
    """ViewSet for listing, retrieving, annotating and deleting runs.
    Runs are created only by a campaign launch (POST /campaign/{id}/launch)
    and by the executor protocol, never through this endpoint.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Login token (Auth0 or Keycloak) authentication is supported for web dashboard use.
    This is a core SDK operation for executing and monitoring security tests.

    Args:
        id (UUID):
        include_results (bool | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Run]
    """

    kwargs = _get_kwargs(
        id=id,
        include_results=include_results,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    id: UUID,
    *,
    client: AuthenticatedClient,
    include_results: bool | Unset = UNSET,
) -> Run | None:
    """ViewSet for listing, retrieving, annotating and deleting runs.
    Runs are created only by a campaign launch (POST /campaign/{id}/launch)
    and by the executor protocol, never through this endpoint.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Login token (Auth0 or Keycloak) authentication is supported for web dashboard use.
    This is a core SDK operation for executing and monitoring security tests.

    Args:
        id (UUID):
        include_results (bool | Unset):

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
            include_results=include_results,
        )
    ).parsed
