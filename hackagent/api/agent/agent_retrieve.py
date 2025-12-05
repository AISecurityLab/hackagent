from http import HTTPStatus
from typing import Any, Optional, Union
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.agent import Agent
from ...types import Response


def _get_kwargs(
    id: UUID,
) -> dict[str, Any]:
    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": f"/agent/{id}",
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[Agent]:
    if response.status_code == 200:
        response_200 = Agent.from_dict(response.json())

        return response_200
    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[Agent]:
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
) -> Response[Agent]:
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
        id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Agent]
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
) -> Optional[Agent]:
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
        id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Agent
    """

    return sync_detailed(
        id=id,
        client=client,
    ).parsed


async def asyncio_detailed(
    id: UUID,
    *,
    client: AuthenticatedClient,
) -> Response[Agent]:
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
        id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Agent]
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
) -> Optional[Agent]:
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
        id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Agent
    """

    return (
        await asyncio_detailed(
            id=id,
            client=client,
        )
    ).parsed
