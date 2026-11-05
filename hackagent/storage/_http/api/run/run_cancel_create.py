from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import Response
from ..models import Run, RunConflict, RunDetailError


def _get_kwargs(
    id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/run/{id}/cancel".format(
            id=quote(str(id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Run | RunConflict | RunDetailError | None:
    if response.status_code == 200:
        response_200 = Run.model_validate(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = RunDetailError.model_validate(response.json())

        return response_400

    if response.status_code == 409:
        response_409 = RunConflict.model_validate(response.json())

        return response_409

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Run | RunConflict | RunDetailError]:
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
) -> Response[Run | RunConflict | RunDetailError]:
    """Cancels a campaign run: a queued run is CANCELLED at once; for a
    running one a cancel is requested, and its executor stops and
    finishes it as CANCELLED.

    Args:
        id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Run | RunConflict | RunDetailError]
    """

    kwargs = _get_kwargs(
        id=id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    id: UUID,
    *,
    client: AuthenticatedClient,
) -> Run | RunConflict | RunDetailError | None:
    """Cancels a campaign run: a queued run is CANCELLED at once; for a
    running one a cancel is requested, and its executor stops and
    finishes it as CANCELLED.

    Args:
        id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Run | RunConflict | RunDetailError
    """

    return sync_detailed(
        id=id,
        client=client,
    ).parsed


async def asyncio_detailed(
    id: UUID,
    *,
    client: AuthenticatedClient,
) -> Response[Run | RunConflict | RunDetailError]:
    """Cancels a campaign run: a queued run is CANCELLED at once; for a
    running one a cancel is requested, and its executor stops and
    finishes it as CANCELLED.

    Args:
        id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Run | RunConflict | RunDetailError]
    """

    kwargs = _get_kwargs(
        id=id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    id: UUID,
    *,
    client: AuthenticatedClient,
) -> Run | RunConflict | RunDetailError | None:
    """Cancels a campaign run: a queued run is CANCELLED at once; for a
    running one a cancel is requested, and its executor stops and
    finishes it as CANCELLED.

    Args:
        id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Run | RunConflict | RunDetailError
    """

    return (
        await asyncio_detailed(
            id=id,
            client=client,
        )
    ).parsed
