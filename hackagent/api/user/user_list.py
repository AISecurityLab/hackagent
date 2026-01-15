from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.paginated_user_profile_list import PaginatedUserProfileList
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
        "url": "/user",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[PaginatedUserProfileList]:
    if response.status_code == 200:
        response_200 = PaginatedUserProfileList.from_dict(response.json())

        return response_200
    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
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
    page: Union[Unset, int] = UNSET,
) -> Response[PaginatedUserProfileList]:
    """Provides access to the UserProfile for the authenticated user.
    Allows updating fields like the linked user's first_name, last_name, email.

    Web-only endpoint - requires Auth0 authentication.
    User profile management requires OAuth context and is not for SDK use.

    Args:
        page (Union[Unset, int]):

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
    page: Union[Unset, int] = UNSET,
) -> Optional[PaginatedUserProfileList]:
    """Provides access to the UserProfile for the authenticated user.
    Allows updating fields like the linked user's first_name, last_name, email.

    Web-only endpoint - requires Auth0 authentication.
    User profile management requires OAuth context and is not for SDK use.

    Args:
        page (Union[Unset, int]):

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
    page: Union[Unset, int] = UNSET,
) -> Response[PaginatedUserProfileList]:
    """Provides access to the UserProfile for the authenticated user.
    Allows updating fields like the linked user's first_name, last_name, email.

    Web-only endpoint - requires Auth0 authentication.
    User profile management requires OAuth context and is not for SDK use.

    Args:
        page (Union[Unset, int]):

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
    page: Union[Unset, int] = UNSET,
) -> Optional[PaginatedUserProfileList]:
    """Provides access to the UserProfile for the authenticated user.
    Allows updating fields like the linked user's first_name, last_name, email.

    Web-only endpoint - requires Auth0 authentication.
    User profile management requires OAuth context and is not for SDK use.

    Args:
        page (Union[Unset, int]):

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
