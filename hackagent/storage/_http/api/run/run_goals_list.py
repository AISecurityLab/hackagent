from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import UNSET, Response, Unset
from ..models import PaginatedRunGoalList


def _get_kwargs(
    id: UUID,
    *,
    page: int | Unset = UNSET,
    page_size: int | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["page"] = page

    params["page_size"] = page_size

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/run/{id}/goals".format(
            id=quote(str(id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> PaginatedRunGoalList | None:
    if response.status_code == 200:
        response_200 = PaginatedRunGoalList.model_validate(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[PaginatedRunGoalList]:
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
    page: int | Unset = UNSET,
    page_size: int | Unset = UNSET,
) -> Response[PaginatedRunGoalList]:
    """Lists the run's goals, one row per goal_index, ordered by goal_index.
    A goal's attempts are the run's results sharing its goal_index;
    results without a goal_index (recorded before clients sent goals)
    are left out.

    Args:
        id (UUID):
        page (int | Unset):
        page_size (int | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[PaginatedRunGoalList]
    """

    kwargs = _get_kwargs(
        id=id,
        page=page,
        page_size=page_size,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    id: UUID,
    *,
    client: AuthenticatedClient,
    page: int | Unset = UNSET,
    page_size: int | Unset = UNSET,
) -> PaginatedRunGoalList | None:
    """Lists the run's goals, one row per goal_index, ordered by goal_index.
    A goal's attempts are the run's results sharing its goal_index;
    results without a goal_index (recorded before clients sent goals)
    are left out.

    Args:
        id (UUID):
        page (int | Unset):
        page_size (int | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        PaginatedRunGoalList
    """

    return sync_detailed(
        id=id,
        client=client,
        page=page,
        page_size=page_size,
    ).parsed


async def asyncio_detailed(
    id: UUID,
    *,
    client: AuthenticatedClient,
    page: int | Unset = UNSET,
    page_size: int | Unset = UNSET,
) -> Response[PaginatedRunGoalList]:
    """Lists the run's goals, one row per goal_index, ordered by goal_index.
    A goal's attempts are the run's results sharing its goal_index;
    results without a goal_index (recorded before clients sent goals)
    are left out.

    Args:
        id (UUID):
        page (int | Unset):
        page_size (int | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[PaginatedRunGoalList]
    """

    kwargs = _get_kwargs(
        id=id,
        page=page,
        page_size=page_size,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    id: UUID,
    *,
    client: AuthenticatedClient,
    page: int | Unset = UNSET,
    page_size: int | Unset = UNSET,
) -> PaginatedRunGoalList | None:
    """Lists the run's goals, one row per goal_index, ordered by goal_index.
    A goal's attempts are the run's results sharing its goal_index;
    results without a goal_index (recorded before clients sent goals)
    are left out.

    Args:
        id (UUID):
        page (int | Unset):
        page_size (int | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        PaginatedRunGoalList
    """

    return (
        await asyncio_detailed(
            id=id,
            client=client,
            page=page,
            page_size=page_size,
        )
    ).parsed
