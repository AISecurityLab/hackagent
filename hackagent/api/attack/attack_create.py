from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import Response
from ..models import Attack, AttackRequest


def _get_kwargs(
    *,
    body: AttackRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/attack",
    }

    _kwargs["json"] = body.model_dump(by_alias=True, mode="json", exclude_none=True)

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Attack | None:
    if response.status_code == 201:
        response_201 = Attack.model_validate(response.json())

        return response_201

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Attack]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: AttackRequest,
) -> Response[Attack]:
    """Manages Attack configurations through standard CRUD operations.

    This ViewSet allows clients to:
    - Create new Attack configurations.
    - List existing Attack configurations (with filtering based on user/org).
    - Retrieve details of a specific Attack configuration.
    - Update an existing Attack configuration.
    - Delete an Attack configuration.

    The actual execution of an attack based on these configurations, and the
    management of run statuses or results, are handled by other parts of the API
    (e.g., potentially a RunViewSet or similar).

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Auth0 authentication is supported as fallback for web dashboard use.

    Attributes:
        queryset: The base queryset, retrieving all Attack objects with related
                  entities (agent, owner, organization) pre-fetched.
        serializer_class: The serializer (`AttackSerializer`) used for data
                          conversion for Attack configurations.
        authentication_classes: API Key (primary) + Auth0 (fallback) authentication.
        permission_classes: List of permission enforcement classes.
        parser_classes: List of parsers for request data (JSONParser).
        lookup_field: The model field used for looking up individual instances ('id').

    Args:
        body (AttackRequest): Serializer for the Attack model, which represents an Attack
            configuration.

            Handles the conversion of Attack configuration instances to JSON (and vice-versa)
            for API requests and responses. It includes read-only fields for related
            object names (like agent_name, owner_username) for convenience in API outputs.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Attack]
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
    body: AttackRequest,
) -> Attack | None:
    """Manages Attack configurations through standard CRUD operations.

    This ViewSet allows clients to:
    - Create new Attack configurations.
    - List existing Attack configurations (with filtering based on user/org).
    - Retrieve details of a specific Attack configuration.
    - Update an existing Attack configuration.
    - Delete an Attack configuration.

    The actual execution of an attack based on these configurations, and the
    management of run statuses or results, are handled by other parts of the API
    (e.g., potentially a RunViewSet or similar).

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Auth0 authentication is supported as fallback for web dashboard use.

    Attributes:
        queryset: The base queryset, retrieving all Attack objects with related
                  entities (agent, owner, organization) pre-fetched.
        serializer_class: The serializer (`AttackSerializer`) used for data
                          conversion for Attack configurations.
        authentication_classes: API Key (primary) + Auth0 (fallback) authentication.
        permission_classes: List of permission enforcement classes.
        parser_classes: List of parsers for request data (JSONParser).
        lookup_field: The model field used for looking up individual instances ('id').

    Args:
        body (AttackRequest): Serializer for the Attack model, which represents an Attack
            configuration.

            Handles the conversion of Attack configuration instances to JSON (and vice-versa)
            for API requests and responses. It includes read-only fields for related
            object names (like agent_name, owner_username) for convenience in API outputs.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Attack
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: AttackRequest,
) -> Response[Attack]:
    """Manages Attack configurations through standard CRUD operations.

    This ViewSet allows clients to:
    - Create new Attack configurations.
    - List existing Attack configurations (with filtering based on user/org).
    - Retrieve details of a specific Attack configuration.
    - Update an existing Attack configuration.
    - Delete an Attack configuration.

    The actual execution of an attack based on these configurations, and the
    management of run statuses or results, are handled by other parts of the API
    (e.g., potentially a RunViewSet or similar).

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Auth0 authentication is supported as fallback for web dashboard use.

    Attributes:
        queryset: The base queryset, retrieving all Attack objects with related
                  entities (agent, owner, organization) pre-fetched.
        serializer_class: The serializer (`AttackSerializer`) used for data
                          conversion for Attack configurations.
        authentication_classes: API Key (primary) + Auth0 (fallback) authentication.
        permission_classes: List of permission enforcement classes.
        parser_classes: List of parsers for request data (JSONParser).
        lookup_field: The model field used for looking up individual instances ('id').

    Args:
        body (AttackRequest): Serializer for the Attack model, which represents an Attack
            configuration.

            Handles the conversion of Attack configuration instances to JSON (and vice-versa)
            for API requests and responses. It includes read-only fields for related
            object names (like agent_name, owner_username) for convenience in API outputs.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Attack]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: AttackRequest,
) -> Attack | None:
    """Manages Attack configurations through standard CRUD operations.

    This ViewSet allows clients to:
    - Create new Attack configurations.
    - List existing Attack configurations (with filtering based on user/org).
    - Retrieve details of a specific Attack configuration.
    - Update an existing Attack configuration.
    - Delete an Attack configuration.

    The actual execution of an attack based on these configurations, and the
    management of run statuses or results, are handled by other parts of the API
    (e.g., potentially a RunViewSet or similar).

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Auth0 authentication is supported as fallback for web dashboard use.

    Attributes:
        queryset: The base queryset, retrieving all Attack objects with related
                  entities (agent, owner, organization) pre-fetched.
        serializer_class: The serializer (`AttackSerializer`) used for data
                          conversion for Attack configurations.
        authentication_classes: API Key (primary) + Auth0 (fallback) authentication.
        permission_classes: List of permission enforcement classes.
        parser_classes: List of parsers for request data (JSONParser).
        lookup_field: The model field used for looking up individual instances ('id').

    Args:
        body (AttackRequest): Serializer for the Attack model, which represents an Attack
            configuration.

            Handles the conversion of Attack configuration instances to JSON (and vice-versa)
            for API requests and responses. It includes read-only fields for related
            object names (like agent_name, owner_username) for convenience in API outputs.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Attack
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
