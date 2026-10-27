from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import UNSET, Response, Unset
from ..models import PatchedRunUpdateRequest, Run


def _get_kwargs(
    id: UUID,
    *,
    body: PatchedRunUpdateRequest | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/run/{id}".format(
            id=quote(str(id), safe=""),
        ),
    }

    if not isinstance(body, Unset):
        _kwargs["json"] = body.model_dump(mode="json", exclude_unset=True)

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
    body: PatchedRunUpdateRequest | Unset = UNSET,
) -> Response[Run]:
    """Update ``run_notes``, or merge keys into ``run_config``. Every other
    field is read-only here.

    Args:
        id (UUID):
        body (PatchedRunUpdateRequest | Unset): What PATCH /run/{id} may change. ``run_config`` is
            merged into the
            stored one, key by key (shallow).

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
    body: PatchedRunUpdateRequest | Unset = UNSET,
) -> Run | None:
    """Update ``run_notes``, or merge keys into ``run_config``. Every other
    field is read-only here.

    Args:
        id (UUID):
        body (PatchedRunUpdateRequest | Unset): What PATCH /run/{id} may change. ``run_config`` is
            merged into the
            stored one, key by key (shallow).

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
    body: PatchedRunUpdateRequest | Unset = UNSET,
) -> Response[Run]:
    """Update ``run_notes``, or merge keys into ``run_config``. Every other
    field is read-only here.

    Args:
        id (UUID):
        body (PatchedRunUpdateRequest | Unset): What PATCH /run/{id} may change. ``run_config`` is
            merged into the
            stored one, key by key (shallow).

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
    body: PatchedRunUpdateRequest | Unset = UNSET,
) -> Run | None:
    """Update ``run_notes``, or merge keys into ``run_config``. Every other
    field is read-only here.

    Args:
        id (UUID):
        body (PatchedRunUpdateRequest | Unset): What PATCH /run/{id} may change. ``run_config`` is
            merged into the
            stored one, key by key (shallow).

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
