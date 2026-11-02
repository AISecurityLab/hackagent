from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import Response
from ..models import Secret, SecretStoreError, SecretValueRequest


def _get_kwargs(
    name: str,
    *,
    body: SecretValueRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "put",
        "url": "/secret/{name}".format(
            name=quote(str(name), safe=""),
        ),
    }

    _kwargs["json"] = body.model_dump(mode="json", exclude_unset=True)

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Secret | SecretStoreError | None:
    if response.status_code == 200:
        response_200 = Secret.model_validate(response.json())

        return response_200

    if response.status_code == 503:
        response_503 = SecretStoreError.model_validate(response.json())

        return response_503

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Secret | SecretStoreError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    name: str,
    *,
    client: AuthenticatedClient,
    body: SecretValueRequest,
) -> Response[Secret | SecretStoreError]:
    """Write-only secret store: values can be set and replaced, never read.

    Args:
        name (str):
        body (SecretValueRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Secret | SecretStoreError]
    """

    kwargs = _get_kwargs(
        name=name,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    name: str,
    *,
    client: AuthenticatedClient,
    body: SecretValueRequest,
) -> Secret | SecretStoreError | None:
    """Write-only secret store: values can be set and replaced, never read.

    Args:
        name (str):
        body (SecretValueRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Secret | SecretStoreError
    """

    return sync_detailed(
        name=name,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    name: str,
    *,
    client: AuthenticatedClient,
    body: SecretValueRequest,
) -> Response[Secret | SecretStoreError]:
    """Write-only secret store: values can be set and replaced, never read.

    Args:
        name (str):
        body (SecretValueRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Secret | SecretStoreError]
    """

    kwargs = _get_kwargs(
        name=name,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    name: str,
    *,
    client: AuthenticatedClient,
    body: SecretValueRequest,
) -> Secret | SecretStoreError | None:
    """Write-only secret store: values can be set and replaced, never read.

    Args:
        name (str):
        body (SecretValueRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Secret | SecretStoreError
    """

    return (
        await asyncio_detailed(
            name=name,
            client=client,
            body=body,
        )
    ).parsed
