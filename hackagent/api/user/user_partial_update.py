from http import HTTPStatus
from typing import Any, Optional, Union
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.patched_user_profile_request import PatchedUserProfileRequest
from ...models.user_profile import UserProfile
from ...types import Response


def _get_kwargs(
    id: UUID,
    *,
    body: Union[
        PatchedUserProfileRequest,
        PatchedUserProfileRequest,
        PatchedUserProfileRequest,
    ],
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": f"/user/{id}",
    }

    if isinstance(body, PatchedUserProfileRequest):
        _kwargs["json"] = body.to_dict()

        headers["Content-Type"] = "application/json"
    if isinstance(body, PatchedUserProfileRequest):
        _kwargs["data"] = body.to_dict()

        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if isinstance(body, PatchedUserProfileRequest):
        _kwargs["files"] = body.to_multipart()

        headers["Content-Type"] = "multipart/form-data"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[UserProfile]:
    if response.status_code == 200:
        response_200 = UserProfile.from_dict(response.json())

        return response_200
    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
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
    body: Union[
        PatchedUserProfileRequest,
        PatchedUserProfileRequest,
        PatchedUserProfileRequest,
    ],
) -> Response[UserProfile]:
    """Provides access to the UserProfile for the authenticated user.
    Allows updating fields like the linked user's first_name, last_name, email.

    Web-only endpoint - requires Auth0 authentication.
    User profile management requires OAuth context and is not for SDK use.

    Args:
        id (UUID):
        body (PatchedUserProfileRequest):
        body (PatchedUserProfileRequest):
        body (PatchedUserProfileRequest):

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
    body: Union[
        PatchedUserProfileRequest,
        PatchedUserProfileRequest,
        PatchedUserProfileRequest,
    ],
) -> Optional[UserProfile]:
    """Provides access to the UserProfile for the authenticated user.
    Allows updating fields like the linked user's first_name, last_name, email.

    Web-only endpoint - requires Auth0 authentication.
    User profile management requires OAuth context and is not for SDK use.

    Args:
        id (UUID):
        body (PatchedUserProfileRequest):
        body (PatchedUserProfileRequest):
        body (PatchedUserProfileRequest):

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
    body: Union[
        PatchedUserProfileRequest,
        PatchedUserProfileRequest,
        PatchedUserProfileRequest,
    ],
) -> Response[UserProfile]:
    """Provides access to the UserProfile for the authenticated user.
    Allows updating fields like the linked user's first_name, last_name, email.

    Web-only endpoint - requires Auth0 authentication.
    User profile management requires OAuth context and is not for SDK use.

    Args:
        id (UUID):
        body (PatchedUserProfileRequest):
        body (PatchedUserProfileRequest):
        body (PatchedUserProfileRequest):

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
    body: Union[
        PatchedUserProfileRequest,
        PatchedUserProfileRequest,
        PatchedUserProfileRequest,
    ],
) -> Optional[UserProfile]:
    """Provides access to the UserProfile for the authenticated user.
    Allows updating fields like the linked user's first_name, last_name, email.

    Web-only endpoint - requires Auth0 authentication.
    User profile management requires OAuth context and is not for SDK use.

    Args:
        id (UUID):
        body (PatchedUserProfileRequest):
        body (PatchedUserProfileRequest):
        body (PatchedUserProfileRequest):

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
