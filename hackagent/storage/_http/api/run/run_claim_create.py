from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import UNSET, Response, Unset
from ..models import ClaimedRun, ClaimRequest, RunConflict


def _get_kwargs(
    id: UUID,
    *,
    body: ClaimRequest | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/run/{id}/claim".format(
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
) -> ClaimedRun | RunConflict | None:
    if response.status_code == 200:
        response_200 = ClaimedRun.model_validate(response.json())

        return response_200

    if response.status_code == 409:
        response_409 = RunConflict.model_validate(response.json())

        return response_409

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ClaimedRun | RunConflict]:
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
    body: ClaimRequest | Unset = UNSET,
) -> Response[ClaimedRun | RunConflict]:
    """Claims a queued campaign run for its executor: a local run with a
    credential of the run's organization, a cloud run with the worker
    token only. The run becomes RUNNING; a run that is not queued any
    more is a 409 naming who has it. A cloud claim also returns the run
    token and the secret values the spec reads (``env``).

    Args:
        id (UUID):
        body (ClaimRequest | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ClaimedRun | RunConflict]
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
    body: ClaimRequest | Unset = UNSET,
) -> ClaimedRun | RunConflict | None:
    """Claims a queued campaign run for its executor: a local run with a
    credential of the run's organization, a cloud run with the worker
    token only. The run becomes RUNNING; a run that is not queued any
    more is a 409 naming who has it. A cloud claim also returns the run
    token and the secret values the spec reads (``env``).

    Args:
        id (UUID):
        body (ClaimRequest | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ClaimedRun | RunConflict
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
    body: ClaimRequest | Unset = UNSET,
) -> Response[ClaimedRun | RunConflict]:
    """Claims a queued campaign run for its executor: a local run with a
    credential of the run's organization, a cloud run with the worker
    token only. The run becomes RUNNING; a run that is not queued any
    more is a 409 naming who has it. A cloud claim also returns the run
    token and the secret values the spec reads (``env``).

    Args:
        id (UUID):
        body (ClaimRequest | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ClaimedRun | RunConflict]
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
    body: ClaimRequest | Unset = UNSET,
) -> ClaimedRun | RunConflict | None:
    """Claims a queued campaign run for its executor: a local run with a
    credential of the run's organization, a cloud run with the worker
    token only. The run becomes RUNNING; a run that is not queued any
    more is a 409 naming who has it. A cloud claim also returns the run
    token and the secret values the spec reads (``env``).

    Args:
        id (UUID):
        body (ClaimRequest | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ClaimedRun | RunConflict
    """

    return (
        await asyncio_detailed(
            id=id,
            client=client,
            body=body,
        )
    ).parsed
