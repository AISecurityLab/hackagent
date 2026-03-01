from http import HTTPStatus
from typing import Any
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import UNSET, Response, Unset
from ..models import PaginatedRunList, StatusEnum


def _get_kwargs(
    *,
    agent: UUID | Unset = UNSET,
    attack: UUID | Unset = UNSET,
    is_client_executed: bool | Unset = UNSET,
    organization: UUID | Unset = UNSET,
    page: int | Unset = UNSET,
    page_size: int | Unset = UNSET,
    status: StatusEnum | Unset = UNSET,
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

    params["is_client_executed"] = is_client_executed

    json_organization: str | Unset = UNSET
    if not isinstance(organization, Unset):
        json_organization = str(organization)
    params["organization"] = json_organization

    params["page"] = page

    params["page_size"] = page_size

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
) -> PaginatedRunList | None:
    if response.status_code == 200:
        response_200 = PaginatedRunList.model_validate(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[PaginatedRunList]:
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
    is_client_executed: bool | Unset = UNSET,
    organization: UUID | Unset = UNSET,
    page: int | Unset = UNSET,
    page_size: int | Unset = UNSET,
    status: StatusEnum | Unset = UNSET,
) -> Response[PaginatedRunList]:
    """ViewSet for managing Run instances.
    Primarily for listing/retrieving runs.
    Creation of server-side runs is handled by custom actions.
    Runs initiated from Attack definitions are created via AttackViewSet.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Auth0 authentication is supported as fallback for web dashboard use.
    This is a core SDK operation for executing and monitoring security tests.

    Args:
        agent (UUID | Unset):
        attack (UUID | Unset):
        is_client_executed (bool | Unset):
        organization (UUID | Unset):
        page (int | Unset):
        page_size (int | Unset):
        status (StatusEnum | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[PaginatedRunList]
    """

    kwargs = _get_kwargs(
        agent=agent,
        attack=attack,
        is_client_executed=is_client_executed,
        organization=organization,
        page=page,
        page_size=page_size,
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
    is_client_executed: bool | Unset = UNSET,
    organization: UUID | Unset = UNSET,
    page: int | Unset = UNSET,
    page_size: int | Unset = UNSET,
    status: StatusEnum | Unset = UNSET,
) -> PaginatedRunList | None:
    """ViewSet for managing Run instances.
    Primarily for listing/retrieving runs.
    Creation of server-side runs is handled by custom actions.
    Runs initiated from Attack definitions are created via AttackViewSet.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Auth0 authentication is supported as fallback for web dashboard use.
    This is a core SDK operation for executing and monitoring security tests.

    Args:
        agent (UUID | Unset):
        attack (UUID | Unset):
        is_client_executed (bool | Unset):
        organization (UUID | Unset):
        page (int | Unset):
        page_size (int | Unset):
        status (StatusEnum | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        PaginatedRunList
    """

    return sync_detailed(
        client=client,
        agent=agent,
        attack=attack,
        is_client_executed=is_client_executed,
        organization=organization,
        page=page,
        page_size=page_size,
        status=status,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    agent: UUID | Unset = UNSET,
    attack: UUID | Unset = UNSET,
    is_client_executed: bool | Unset = UNSET,
    organization: UUID | Unset = UNSET,
    page: int | Unset = UNSET,
    page_size: int | Unset = UNSET,
    status: StatusEnum | Unset = UNSET,
) -> Response[PaginatedRunList]:
    """ViewSet for managing Run instances.
    Primarily for listing/retrieving runs.
    Creation of server-side runs is handled by custom actions.
    Runs initiated from Attack definitions are created via AttackViewSet.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Auth0 authentication is supported as fallback for web dashboard use.
    This is a core SDK operation for executing and monitoring security tests.

    Args:
        agent (UUID | Unset):
        attack (UUID | Unset):
        is_client_executed (bool | Unset):
        organization (UUID | Unset):
        page (int | Unset):
        page_size (int | Unset):
        status (StatusEnum | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[PaginatedRunList]
    """

    kwargs = _get_kwargs(
        agent=agent,
        attack=attack,
        is_client_executed=is_client_executed,
        organization=organization,
        page=page,
        page_size=page_size,
        status=status,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    agent: UUID | Unset = UNSET,
    attack: UUID | Unset = UNSET,
    is_client_executed: bool | Unset = UNSET,
    organization: UUID | Unset = UNSET,
    page: int | Unset = UNSET,
    page_size: int | Unset = UNSET,
    status: StatusEnum | Unset = UNSET,
) -> PaginatedRunList | None:
    """ViewSet for managing Run instances.
    Primarily for listing/retrieving runs.
    Creation of server-side runs is handled by custom actions.
    Runs initiated from Attack definitions are created via AttackViewSet.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Auth0 authentication is supported as fallback for web dashboard use.
    This is a core SDK operation for executing and monitoring security tests.

    Args:
        agent (UUID | Unset):
        attack (UUID | Unset):
        is_client_executed (bool | Unset):
        organization (UUID | Unset):
        page (int | Unset):
        page_size (int | Unset):
        status (StatusEnum | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        PaginatedRunList
    """

    return (
        await asyncio_detailed(
            client=client,
            agent=agent,
            attack=attack,
            is_client_executed=is_client_executed,
            organization=organization,
            page=page,
            page_size=page_size,
            status=status,
        )
    ).parsed
