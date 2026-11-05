from http import HTTPStatus
from typing import Any, cast

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import Response
from ..models import Secret, SecretStoreError, SecretWriteRequest


def _get_kwargs(
    *,
    body: SecretWriteRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/secret",
    }

    _kwargs["json"] = body.model_dump(mode="json", exclude_unset=True)

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Any | Secret | SecretStoreError | None:
    if response.status_code == 201:
        response_201 = Secret.model_validate(response.json())

        return response_201

    if response.status_code == 400:
        response_400 = cast(Any, None)
        return response_400

    if response.status_code == 503:
        response_503 = SecretStoreError.model_validate(response.json())

        return response_503

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Any | Secret | SecretStoreError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: SecretWriteRequest,
) -> Response[Any | Secret | SecretStoreError]:
    """Write-only secret store: values can be set and replaced, never read.

    Args:
        body (SecretWriteRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | Secret | SecretStoreError]
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
    body: SecretWriteRequest,
) -> Any | Secret | SecretStoreError | None:
    """Write-only secret store: values can be set and replaced, never read.

    Args:
        body (SecretWriteRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | Secret | SecretStoreError
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: SecretWriteRequest,
) -> Response[Any | Secret | SecretStoreError]:
    """Write-only secret store: values can be set and replaced, never read.

    Args:
        body (SecretWriteRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | Secret | SecretStoreError]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: SecretWriteRequest,
) -> Any | Secret | SecretStoreError | None:
    """Write-only secret store: values can be set and replaced, never read.

    Args:
        body (SecretWriteRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | Secret | SecretStoreError
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
