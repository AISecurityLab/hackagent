from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import UNSET, Response, Unset
from ..models import ChildRunRequest, Run, RunConflict, RunDetailError


def _get_kwargs(
    id: UUID,
    *,
    body: ChildRunRequest | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/run/{id}/children".format(
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
) -> Run | RunConflict | RunDetailError | None:
    if response.status_code == 201:
        response_201 = Run.model_validate(response.json())

        return response_201

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
    body: ChildRunRequest | Unset = UNSET,
) -> Response[Run | RunConflict | RunDetailError]:
    """Creates a child run (one attack) of a running campaign run, for its
    executor. The child is RUNNING, with the campaign run's executor,
    organization, owner and campaign.

    Args:
        id (UUID):
        body (ChildRunRequest | Unset): A child run of a campaign run: one attack. The agent
            defaults to the
            campaign run's.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Run | RunConflict | RunDetailError]
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
    body: ChildRunRequest | Unset = UNSET,
) -> Run | RunConflict | RunDetailError | None:
    """Creates a child run (one attack) of a running campaign run, for its
    executor. The child is RUNNING, with the campaign run's executor,
    organization, owner and campaign.

    Args:
        id (UUID):
        body (ChildRunRequest | Unset): A child run of a campaign run: one attack. The agent
            defaults to the
            campaign run's.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Run | RunConflict | RunDetailError
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
    body: ChildRunRequest | Unset = UNSET,
) -> Response[Run | RunConflict | RunDetailError]:
    """Creates a child run (one attack) of a running campaign run, for its
    executor. The child is RUNNING, with the campaign run's executor,
    organization, owner and campaign.

    Args:
        id (UUID):
        body (ChildRunRequest | Unset): A child run of a campaign run: one attack. The agent
            defaults to the
            campaign run's.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Run | RunConflict | RunDetailError]
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
    body: ChildRunRequest | Unset = UNSET,
) -> Run | RunConflict | RunDetailError | None:
    """Creates a child run (one attack) of a running campaign run, for its
    executor. The child is RUNNING, with the campaign run's executor,
    organization, owner and campaign.

    Args:
        id (UUID):
        body (ChildRunRequest | Unset): A child run of a campaign run: one attack. The agent
            defaults to the
            campaign run's.

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
            body=body,
        )
    ).parsed
