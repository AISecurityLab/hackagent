from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import UNSET, Response, Unset
from ..models import PaginatedUserProfileList


def _get_kwargs(
    *,
    page: int | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["page"] = page

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/user",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> PaginatedUserProfileList | None:
    if response.status_code == 200:
        response_200 = PaginatedUserProfileList.model_validate(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[PaginatedUserProfileList]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    page: int | Unset = UNSET,
) -> Response[PaginatedUserProfileList]:
    """Provides access to the UserProfile for the authenticated user.
    Allows updating fields like the linked user's first_name, last_name, email.

    Web-only endpoint - requires Auth0 authentication.
    User profile management requires OAuth context and is not for SDK use.

    Args:
        page (int | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[PaginatedUserProfileList]
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
    page: int | Unset = UNSET,
) -> PaginatedUserProfileList | None:
    """Provides access to the UserProfile for the authenticated user.
    Allows updating fields like the linked user's first_name, last_name, email.

    Web-only endpoint - requires Auth0 authentication.
    User profile management requires OAuth context and is not for SDK use.

    Args:
        page (int | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        PaginatedUserProfileList
    """

    return sync_detailed(
        client=client,
        page=page,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    page: int | Unset = UNSET,
) -> Response[PaginatedUserProfileList]:
    """Provides access to the UserProfile for the authenticated user.
    Allows updating fields like the linked user's first_name, last_name, email.

    Web-only endpoint - requires Auth0 authentication.
    User profile management requires OAuth context and is not for SDK use.

    Args:
        page (int | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[PaginatedUserProfileList]
    """

    kwargs = _get_kwargs(
        page=page,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    page: int | Unset = UNSET,
) -> PaginatedUserProfileList | None:
    """Provides access to the UserProfile for the authenticated user.
    Allows updating fields like the linked user's first_name, last_name, email.

    Web-only endpoint - requires Auth0 authentication.
    User profile management requires OAuth context and is not for SDK use.

    Args:
        page (int | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        PaginatedUserProfileList
    """

    return (
        await asyncio_detailed(
            client=client,
            page=page,
        )
    ).parsed
