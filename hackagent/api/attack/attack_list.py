from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.paginated_attack_list import PaginatedAttackList
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
        "url": "/attack",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[PaginatedAttackList]:
    if response.status_code == 200:
        response_200 = PaginatedAttackList.from_dict(response.json())

        return response_200
    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[PaginatedAttackList]:
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
) -> Response[PaginatedAttackList]:
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
        page (Union[Unset, int]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[PaginatedAttackList]
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
) -> Optional[PaginatedAttackList]:
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
        page (Union[Unset, int]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        PaginatedAttackList
    """

    return sync_detailed(
        client=client,
        page=page,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    page: Union[Unset, int] = UNSET,
) -> Response[PaginatedAttackList]:
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
        page (Union[Unset, int]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[PaginatedAttackList]
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
) -> Optional[PaginatedAttackList]:
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
        page (Union[Unset, int]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        PaginatedAttackList
    """

    return (
        await asyncio_detailed(
            client=client,
            page=page,
        )
    ).parsed
