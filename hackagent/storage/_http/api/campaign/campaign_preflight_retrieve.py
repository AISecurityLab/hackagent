from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import UNSET, Response
from ..models import CampaignPreflightRetrieveExecutor, LaunchError, Preflight


def _get_kwargs(
    id: UUID,
    *,
    executor: CampaignPreflightRetrieveExecutor,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_executor = executor.value
    params["executor"] = json_executor

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/campaign/{id}/preflight".format(
            id=quote(str(id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> LaunchError | Preflight | None:
    if response.status_code == 200:
        response_200 = Preflight.model_validate(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = LaunchError.model_validate(response.json())

        return response_400

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[LaunchError | Preflight]:
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
    executor: CampaignPreflightRetrieveExecutor,
) -> Response[LaunchError | Preflight]:
    """The problems a launch with ``?executor=cloud|local`` would refuse.

    Args:
        id (UUID):
        executor (CampaignPreflightRetrieveExecutor):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[LaunchError | Preflight]
    """

    kwargs = _get_kwargs(
        id=id,
        executor=executor,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    id: UUID,
    *,
    client: AuthenticatedClient,
    executor: CampaignPreflightRetrieveExecutor,
) -> LaunchError | Preflight | None:
    """The problems a launch with ``?executor=cloud|local`` would refuse.

    Args:
        id (UUID):
        executor (CampaignPreflightRetrieveExecutor):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        LaunchError | Preflight
    """

    return sync_detailed(
        id=id,
        client=client,
        executor=executor,
    ).parsed


async def asyncio_detailed(
    id: UUID,
    *,
    client: AuthenticatedClient,
    executor: CampaignPreflightRetrieveExecutor,
) -> Response[LaunchError | Preflight]:
    """The problems a launch with ``?executor=cloud|local`` would refuse.

    Args:
        id (UUID):
        executor (CampaignPreflightRetrieveExecutor):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[LaunchError | Preflight]
    """

    kwargs = _get_kwargs(
        id=id,
        executor=executor,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    id: UUID,
    *,
    client: AuthenticatedClient,
    executor: CampaignPreflightRetrieveExecutor,
) -> LaunchError | Preflight | None:
    """The problems a launch with ``?executor=cloud|local`` would refuse.

    Args:
        id (UUID):
        executor (CampaignPreflightRetrieveExecutor):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        LaunchError | Preflight
    """

    return (
        await asyncio_detailed(
            id=id,
            client=client,
            executor=executor,
        )
    ).parsed
