from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import UNSET, Response, Unset
from ..models import Organization, OrganizationRequest


def _get_kwargs(
    *,
    body: OrganizationRequest
    | OrganizationRequest
    | OrganizationRequest
    | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/organization",
    }

    if isinstance(body, OrganizationRequest):
        _kwargs["json"] = body.model_dump(by_alias=True, mode="json", exclude_none=True)

        headers["Content-Type"] = "application/json"
    if isinstance(body, OrganizationRequest):
        _kwargs["data"] = body.model_dump(by_alias=True, mode="json", exclude_none=True)

        headers["Content-Type"] = "application/x-www-form-urlencoded"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Organization | None:
    if response.status_code == 201:
        response_201 = Organization.model_validate(response.json())

        return response_201

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Organization]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: OrganizationRequest
    | OrganizationRequest
    | OrganizationRequest
    | Unset = UNSET,
) -> Response[Organization]:
    """Provides access to Organization details for the authenticated user.

    Web-only endpoint - requires Auth0 authentication.
    Organization management and billing operations require browser context.

    Args:
        body (OrganizationRequest):
        body (OrganizationRequest):
        body (OrganizationRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Organization]
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
    body: OrganizationRequest
    | OrganizationRequest
    | OrganizationRequest
    | Unset = UNSET,
) -> Organization | None:
    """Provides access to Organization details for the authenticated user.

    Web-only endpoint - requires Auth0 authentication.
    Organization management and billing operations require browser context.

    Args:
        body (OrganizationRequest):
        body (OrganizationRequest):
        body (OrganizationRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Organization
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: OrganizationRequest
    | OrganizationRequest
    | OrganizationRequest
    | Unset = UNSET,
) -> Response[Organization]:
    """Provides access to Organization details for the authenticated user.

    Web-only endpoint - requires Auth0 authentication.
    Organization management and billing operations require browser context.

    Args:
        body (OrganizationRequest):
        body (OrganizationRequest):
        body (OrganizationRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Organization]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: OrganizationRequest
    | OrganizationRequest
    | OrganizationRequest
    | Unset = UNSET,
) -> Organization | None:
    """Provides access to Organization details for the authenticated user.

    Web-only endpoint - requires Auth0 authentication.
    Organization management and billing operations require browser context.

    Args:
        body (OrganizationRequest):
        body (OrganizationRequest):
        body (OrganizationRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Organization
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
