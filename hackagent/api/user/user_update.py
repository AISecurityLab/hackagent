from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import UNSET, Response, Unset
from ..models import UserProfile, UserProfileRequest


def _get_kwargs(
    id: UUID,
    *,
    body: UserProfileRequest | UserProfileRequest | UserProfileRequest | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "put",
        "url": "/user/{id}".format(
            id=quote(str(id), safe=""),
        ),
    }

    if isinstance(body, UserProfileRequest):
        if not isinstance(body, Unset):
            _kwargs["json"] = body.model_dump(
                by_alias=True, mode="json", exclude_none=True
            )

        headers["Content-Type"] = "application/json"
    if isinstance(body, UserProfileRequest):
        if not isinstance(body, Unset):
            _kwargs["data"] = body.model_dump(
                by_alias=True, mode="json", exclude_none=True
            )

        headers["Content-Type"] = "application/x-www-form-urlencoded"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> UserProfile | None:
    if response.status_code == 200:
        response_200 = UserProfile.model_validate(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[UserProfile]:
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
    body: UserProfileRequest | UserProfileRequest | UserProfileRequest | Unset = UNSET,
) -> Response[UserProfile]:
    """Provides access to the UserProfile for the authenticated user.
    Allows updating fields like the linked user's first_name, last_name, email.

    Web-only endpoint - requires Auth0 authentication.
    User profile management requires OAuth context and is not for SDK use.

    Args:
        id (UUID):
        body (UserProfileRequest | Unset):
        body (UserProfileRequest | Unset):
        body (UserProfileRequest | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[UserProfile]
    """

    kwargs = _get_kwargs(
        id=id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    id: UUID,
    *,
    client: AuthenticatedClient,
    body: UserProfileRequest | UserProfileRequest | UserProfileRequest | Unset = UNSET,
) -> UserProfile | None:
    """Provides access to the UserProfile for the authenticated user.
    Allows updating fields like the linked user's first_name, last_name, email.

    Web-only endpoint - requires Auth0 authentication.
    User profile management requires OAuth context and is not for SDK use.

    Args:
        id (UUID):
        body (UserProfileRequest | Unset):
        body (UserProfileRequest | Unset):
        body (UserProfileRequest | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        UserProfile
    """

    return sync_detailed(
        id=id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    id: UUID,
    *,
    client: AuthenticatedClient,
    body: UserProfileRequest | UserProfileRequest | UserProfileRequest | Unset = UNSET,
) -> Response[UserProfile]:
    """Provides access to the UserProfile for the authenticated user.
    Allows updating fields like the linked user's first_name, last_name, email.

    Web-only endpoint - requires Auth0 authentication.
    User profile management requires OAuth context and is not for SDK use.

    Args:
        id (UUID):
        body (UserProfileRequest | Unset):
        body (UserProfileRequest | Unset):
        body (UserProfileRequest | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[UserProfile]
    """

    kwargs = _get_kwargs(
        id=id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    id: UUID,
    *,
    client: AuthenticatedClient,
    body: UserProfileRequest | UserProfileRequest | UserProfileRequest | Unset = UNSET,
) -> UserProfile | None:
    """Provides access to the UserProfile for the authenticated user.
    Allows updating fields like the linked user's first_name, last_name, email.

    Web-only endpoint - requires Auth0 authentication.
    User profile management requires OAuth context and is not for SDK use.

    Args:
        id (UUID):
        body (UserProfileRequest | Unset):
        body (UserProfileRequest | Unset):
        body (UserProfileRequest | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        UserProfile
    """

    return (
        await asyncio_detailed(
            id=id,
            client=client,
            body=body,
        )
    ).parsed
