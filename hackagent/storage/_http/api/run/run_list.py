from http import HTTPStatus
from typing import Any
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import UNSET, Response, Unset
from ..models import PaginatedRunSummaryList, RunListExecutor, RunListStatus


def _get_kwargs(
    *,
    agent: UUID | Unset = UNSET,
    attack: UUID | Unset = UNSET,
    campaign: UUID | Unset = UNSET,
    executor: RunListExecutor | Unset = UNSET,
    organization: UUID | Unset = UNSET,
    page: int | Unset = UNSET,
    page_size: int | Unset = UNSET,
    parent: UUID | Unset = UNSET,
    parent_isnull: bool | Unset = UNSET,
    status: RunListStatus | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_agent: str | Unset = UNSET
    if not isinstance(agent, Unset):
        json_agent = str(agent)
    params["agent"] = json_agent

    json_attack: str | Unset = UNSET
    if not isinstance(attack, Unset):
        json_attack = str(attack)
    params["attack"] = json_attack

    json_campaign: str | Unset = UNSET
    if not isinstance(campaign, Unset):
        json_campaign = str(campaign)
    params["campaign"] = json_campaign

    json_executor: str | Unset = UNSET
    if not isinstance(executor, Unset):
        json_executor = executor.value

    params["executor"] = json_executor

    json_organization: str | Unset = UNSET
    if not isinstance(organization, Unset):
        json_organization = str(organization)
    params["organization"] = json_organization

    params["page"] = page

    params["page_size"] = page_size

    json_parent: str | Unset = UNSET
    if not isinstance(parent, Unset):
        json_parent = str(parent)
    params["parent"] = json_parent

    params["parent__isnull"] = parent_isnull

    json_status: str | Unset = UNSET
    if not isinstance(status, Unset):
        json_status = status.value

    params["status"] = json_status

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/run",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> PaginatedRunSummaryList | None:
    if response.status_code == 200:
        response_200 = PaginatedRunSummaryList.model_validate(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[PaginatedRunSummaryList]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    agent: UUID | Unset = UNSET,
    attack: UUID | Unset = UNSET,
    campaign: UUID | Unset = UNSET,
    executor: RunListExecutor | Unset = UNSET,
    organization: UUID | Unset = UNSET,
    page: int | Unset = UNSET,
    page_size: int | Unset = UNSET,
    parent: UUID | Unset = UNSET,
    parent_isnull: bool | Unset = UNSET,
    status: RunListStatus | Unset = UNSET,
) -> Response[PaginatedRunSummaryList]:
    """ViewSet for listing, retrieving, annotating and deleting runs.
    Runs are created only by a campaign launch (POST /campaign/{id}/launch)
    and by the executor protocol, never through this endpoint.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Login token (Auth0 or Keycloak) authentication is supported for web dashboard use.
    This is a core SDK operation for executing and monitoring security tests.

    Args:
        agent (UUID | Unset):
        attack (UUID | Unset):
        campaign (UUID | Unset):
        executor (RunListExecutor | Unset):
        organization (UUID | Unset):
        page (int | Unset):
        page_size (int | Unset):
        parent (UUID | Unset):
        parent_isnull (bool | Unset):
        status (RunListStatus | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[PaginatedRunSummaryList]
    """

    kwargs = _get_kwargs(
        agent=agent,
        attack=attack,
        campaign=campaign,
        executor=executor,
        organization=organization,
        page=page,
        page_size=page_size,
        parent=parent,
        parent_isnull=parent_isnull,
        status=status,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    agent: UUID | Unset = UNSET,
    attack: UUID | Unset = UNSET,
    campaign: UUID | Unset = UNSET,
    executor: RunListExecutor | Unset = UNSET,
    organization: UUID | Unset = UNSET,
    page: int | Unset = UNSET,
    page_size: int | Unset = UNSET,
    parent: UUID | Unset = UNSET,
    parent_isnull: bool | Unset = UNSET,
    status: RunListStatus | Unset = UNSET,
) -> PaginatedRunSummaryList | None:
    """ViewSet for listing, retrieving, annotating and deleting runs.
    Runs are created only by a campaign launch (POST /campaign/{id}/launch)
    and by the executor protocol, never through this endpoint.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Login token (Auth0 or Keycloak) authentication is supported for web dashboard use.
    This is a core SDK operation for executing and monitoring security tests.

    Args:
        agent (UUID | Unset):
        attack (UUID | Unset):
        campaign (UUID | Unset):
        executor (RunListExecutor | Unset):
        organization (UUID | Unset):
        page (int | Unset):
        page_size (int | Unset):
        parent (UUID | Unset):
        parent_isnull (bool | Unset):
        status (RunListStatus | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        PaginatedRunSummaryList
    """

    return sync_detailed(
        client=client,
        agent=agent,
        attack=attack,
        campaign=campaign,
        executor=executor,
        organization=organization,
        page=page,
        page_size=page_size,
        parent=parent,
        parent_isnull=parent_isnull,
        status=status,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    agent: UUID | Unset = UNSET,
    attack: UUID | Unset = UNSET,
    campaign: UUID | Unset = UNSET,
    executor: RunListExecutor | Unset = UNSET,
    organization: UUID | Unset = UNSET,
    page: int | Unset = UNSET,
    page_size: int | Unset = UNSET,
    parent: UUID | Unset = UNSET,
    parent_isnull: bool | Unset = UNSET,
    status: RunListStatus | Unset = UNSET,
) -> Response[PaginatedRunSummaryList]:
    """ViewSet for listing, retrieving, annotating and deleting runs.
    Runs are created only by a campaign launch (POST /campaign/{id}/launch)
    and by the executor protocol, never through this endpoint.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Login token (Auth0 or Keycloak) authentication is supported for web dashboard use.
    This is a core SDK operation for executing and monitoring security tests.

    Args:
        agent (UUID | Unset):
        attack (UUID | Unset):
        campaign (UUID | Unset):
        executor (RunListExecutor | Unset):
        organization (UUID | Unset):
        page (int | Unset):
        page_size (int | Unset):
        parent (UUID | Unset):
        parent_isnull (bool | Unset):
        status (RunListStatus | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[PaginatedRunSummaryList]
    """

    kwargs = _get_kwargs(
        agent=agent,
        attack=attack,
        campaign=campaign,
        executor=executor,
        organization=organization,
        page=page,
        page_size=page_size,
        parent=parent,
        parent_isnull=parent_isnull,
        status=status,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    agent: UUID | Unset = UNSET,
    attack: UUID | Unset = UNSET,
    campaign: UUID | Unset = UNSET,
    executor: RunListExecutor | Unset = UNSET,
    organization: UUID | Unset = UNSET,
    page: int | Unset = UNSET,
    page_size: int | Unset = UNSET,
    parent: UUID | Unset = UNSET,
    parent_isnull: bool | Unset = UNSET,
    status: RunListStatus | Unset = UNSET,
) -> PaginatedRunSummaryList | None:
    """ViewSet for listing, retrieving, annotating and deleting runs.
    Runs are created only by a campaign launch (POST /campaign/{id}/launch)
    and by the executor protocol, never through this endpoint.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Login token (Auth0 or Keycloak) authentication is supported for web dashboard use.
    This is a core SDK operation for executing and monitoring security tests.

    Args:
        agent (UUID | Unset):
        attack (UUID | Unset):
        campaign (UUID | Unset):
        executor (RunListExecutor | Unset):
        organization (UUID | Unset):
        page (int | Unset):
        page_size (int | Unset):
        parent (UUID | Unset):
        parent_isnull (bool | Unset):
        status (RunListStatus | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        PaginatedRunSummaryList
    """

    return (
        await asyncio_detailed(
            client=client,
            agent=agent,
            attack=attack,
            campaign=campaign,
            executor=executor,
            organization=organization,
            page=page,
            page_size=page_size,
            parent=parent,
            parent_isnull=parent_isnull,
            status=status,
        )
    ).parsed
