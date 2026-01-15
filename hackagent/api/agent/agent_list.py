from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.paginated_agent_list import PaginatedAgentList
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    page: Union[Unset, int] = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    params["page"] = page

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/agent",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[PaginatedAgentList]:
    if response.status_code == 200:
        response_200 = PaginatedAgentList.from_dict(response.json())

        return response_200
    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[PaginatedAgentList]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    page: Union[Unset, int] = UNSET,
) -> Response[PaginatedAgentList]:
    """Provides CRUD operations for Agent instances.

    This ViewSet manages Agent records, ensuring that users can only interact
    with agents based on their permissions and organizational context.
    It filters agent listings for users and handles the logic for creating
    agents, including associating them with the correct organization and owner.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Auth0 authentication is supported as fallback for web dashboard use.

    Permissions are based on IsAuthenticated, with queryset filtering providing
    row-level access control.

    Class Attributes:
        queryset (QuerySet): The default queryset for listing agents, initially all agents.
                             This is further filtered by `get_queryset()`.
        serializer_class (AgentSerializer): The serializer used for validating and
                                          deserializing input, and for serializing output.
        authentication_classes (list): API Key (primary) + Auth0 (fallback) authentication.
        permission_classes (list): List of permission classes to use.
        parser_classes (list): List of parser classes for handling request data.
        lookup_field (str): The model field used for looking up individual instances (UUID 'id').

    Args:
        page (Union[Unset, int]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[PaginatedAgentList]
    """

    kwargs = _get_kwargs(
        page=page,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    page: Union[Unset, int] = UNSET,
) -> Optional[PaginatedAgentList]:
    """Provides CRUD operations for Agent instances.

    This ViewSet manages Agent records, ensuring that users can only interact
    with agents based on their permissions and organizational context.
    It filters agent listings for users and handles the logic for creating
    agents, including associating them with the correct organization and owner.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Auth0 authentication is supported as fallback for web dashboard use.

    Permissions are based on IsAuthenticated, with queryset filtering providing
    row-level access control.

    Class Attributes:
        queryset (QuerySet): The default queryset for listing agents, initially all agents.
                             This is further filtered by `get_queryset()`.
        serializer_class (AgentSerializer): The serializer used for validating and
                                          deserializing input, and for serializing output.
        authentication_classes (list): API Key (primary) + Auth0 (fallback) authentication.
        permission_classes (list): List of permission classes to use.
        parser_classes (list): List of parser classes for handling request data.
        lookup_field (str): The model field used for looking up individual instances (UUID 'id').

    Args:
        page (Union[Unset, int]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        PaginatedAgentList
    """

    return sync_detailed(
        client=client,
        page=page,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    page: Union[Unset, int] = UNSET,
) -> Response[PaginatedAgentList]:
    """Provides CRUD operations for Agent instances.

    This ViewSet manages Agent records, ensuring that users can only interact
    with agents based on their permissions and organizational context.
    It filters agent listings for users and handles the logic for creating
    agents, including associating them with the correct organization and owner.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Auth0 authentication is supported as fallback for web dashboard use.

    Permissions are based on IsAuthenticated, with queryset filtering providing
    row-level access control.

    Class Attributes:
        queryset (QuerySet): The default queryset for listing agents, initially all agents.
                             This is further filtered by `get_queryset()`.
        serializer_class (AgentSerializer): The serializer used for validating and
                                          deserializing input, and for serializing output.
        authentication_classes (list): API Key (primary) + Auth0 (fallback) authentication.
        permission_classes (list): List of permission classes to use.
        parser_classes (list): List of parser classes for handling request data.
        lookup_field (str): The model field used for looking up individual instances (UUID 'id').

    Args:
        page (Union[Unset, int]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[PaginatedAgentList]
    """

    kwargs = _get_kwargs(
        page=page,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    page: Union[Unset, int] = UNSET,
) -> Optional[PaginatedAgentList]:
    """Provides CRUD operations for Agent instances.

    This ViewSet manages Agent records, ensuring that users can only interact
    with agents based on their permissions and organizational context.
    It filters agent listings for users and handles the logic for creating
    agents, including associating them with the correct organization and owner.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Auth0 authentication is supported as fallback for web dashboard use.

    Permissions are based on IsAuthenticated, with queryset filtering providing
    row-level access control.

    Class Attributes:
        queryset (QuerySet): The default queryset for listing agents, initially all agents.
                             This is further filtered by `get_queryset()`.
        serializer_class (AgentSerializer): The serializer used for validating and
                                          deserializing input, and for serializing output.
        authentication_classes (list): API Key (primary) + Auth0 (fallback) authentication.
        permission_classes (list): List of permission classes to use.
        parser_classes (list): List of parser classes for handling request data.
        lookup_field (str): The model field used for looking up individual instances (UUID 'id').

    Args:
        page (Union[Unset, int]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        PaginatedAgentList
    """

    return (
        await asyncio_detailed(
            client=client,
            page=page,
        )
    ).parsed
