from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import Response
from ..models import Trace, TraceRequest


def _get_kwargs(
    id: UUID,
    *,
    body: TraceRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/result/{id}/trace".format(
            id=quote(str(id), safe=""),
        ),
    }

    _kwargs["json"] = body.model_dump(by_alias=True, mode="json", exclude_none=True)

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Trace | None:
    if response.status_code == 201:
        response_201 = Trace.model_validate(response.json())

        return response_201

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Trace]:
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
    body: TraceRequest,
) -> Response[Trace]:
    """Creates a new Trace associated with this Result.
    The result instance is fetched using the 'id' (the lookup_field) from the URL.

    Args:
        id (UUID):
        body (TraceRequest): Serializer for the Trace model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Trace]
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
    body: TraceRequest,
) -> Trace | None:
    """Creates a new Trace associated with this Result.
    The result instance is fetched using the 'id' (the lookup_field) from the URL.

    Args:
        id (UUID):
        body (TraceRequest): Serializer for the Trace model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Trace
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
    body: TraceRequest,
) -> Response[Trace]:
    """Creates a new Trace associated with this Result.
    The result instance is fetched using the 'id' (the lookup_field) from the URL.

    Args:
        id (UUID):
        body (TraceRequest): Serializer for the Trace model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Trace]
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
    body: TraceRequest,
) -> Trace | None:
    """Creates a new Trace associated with this Result.
    The result instance is fetched using the 'id' (the lookup_field) from the URL.

    Args:
        id (UUID):
        body (TraceRequest): Serializer for the Trace model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Trace
    """

    return (
        await asyncio_detailed(
            id=id,
            client=client,
            body=body,
        )
    ).parsed
