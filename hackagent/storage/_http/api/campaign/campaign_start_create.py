from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import Response
from ..models import CampaignStartRequest, Run


def _get_kwargs(
    *,
    body: CampaignStartRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/campaign/start",
    }

    _kwargs["json"] = body.model_dump(mode="json", exclude_unset=True)

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Run | None:
    if response.status_code == 201:
        response_201 = Run.model_validate(response.json())

        return response_201

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
    *,
    client: AuthenticatedClient,
    body: CampaignStartRequest,
) -> Response[Run]:
    """Save the campaign of ``hackagent campaign run FILE`` (by name, in
    the caller's organization) and create its run, already claimed by
    the calling process: it heartbeats and finishes like any executor.

    Args:
        body (CampaignStartRequest): A campaign started by ``hackagent campaign run FILE``: the
            SDK's
            recorded spec, whose ``target`` and ``execution`` are the client's own and
            are not stored.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Run]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    body: CampaignStartRequest,
) -> Run | None:
    """Save the campaign of ``hackagent campaign run FILE`` (by name, in
    the caller's organization) and create its run, already claimed by
    the calling process: it heartbeats and finishes like any executor.

    Args:
        body (CampaignStartRequest): A campaign started by ``hackagent campaign run FILE``: the
            SDK's
            recorded spec, whose ``target`` and ``execution`` are the client's own and
            are not stored.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Run
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: CampaignStartRequest,
) -> Response[Run]:
    """Save the campaign of ``hackagent campaign run FILE`` (by name, in
    the caller's organization) and create its run, already claimed by
    the calling process: it heartbeats and finishes like any executor.

    Args:
        body (CampaignStartRequest): A campaign started by ``hackagent campaign run FILE``: the
            SDK's
            recorded spec, whose ``target`` and ``execution`` are the client's own and
            are not stored.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Run]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: CampaignStartRequest,
) -> Run | None:
    """Save the campaign of ``hackagent campaign run FILE`` (by name, in
    the caller's organization) and create its run, already claimed by
    the calling process: it heartbeats and finishes like any executor.

    Args:
        body (CampaignStartRequest): A campaign started by ``hackagent campaign run FILE``: the
            SDK's
            recorded spec, whose ``target`` and ``execution`` are the client's own and
            are not stored.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Run
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
