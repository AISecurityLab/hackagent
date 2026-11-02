from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import UNSET, Response, Unset
from ..models import CreditRequestRequest, CreditRequestResponse


def _get_kwargs(
    *,
    body: CreditRequestRequest
    | CreditRequestRequest
    | CreditRequestRequest
    | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/credits/request",
    }

    if isinstance(body, CreditRequestRequest):
        if not isinstance(body, Unset):
            _kwargs["json"] = body.model_dump(mode="json", exclude_unset=True)

        headers["Content-Type"] = "application/json"
    elif isinstance(body, CreditRequestRequest):
        if not isinstance(body, Unset):
            _kwargs["data"] = body.model_dump(mode="json", exclude_unset=True)

        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif isinstance(body, CreditRequestRequest):
        if not isinstance(body, Unset):
            _kwargs["files"] = {
                k: (None, str(v))
                for k, v in body.model_dump(mode="json", exclude_unset=True).items()
                if v is not None
            }

        headers["Content-Type"] = "multipart/form-data"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> CreditRequestResponse | None:
    if response.status_code == 200:
        response_200 = CreditRequestResponse.model_validate(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[CreditRequestResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: CreditRequestRequest
    | CreditRequestRequest
    | CreditRequestRequest
    | Unset = UNSET,
) -> Response[CreditRequestResponse]:
    """Request additional credits

     Sends an email to the configured admin asking for more credits.

    Args:
        body (CreditRequestRequest | Unset):
        body (CreditRequestRequest | Unset):
        body (CreditRequestRequest | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreditRequestResponse]
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
    body: CreditRequestRequest
    | CreditRequestRequest
    | CreditRequestRequest
    | Unset = UNSET,
) -> CreditRequestResponse | None:
    """Request additional credits

     Sends an email to the configured admin asking for more credits.

    Args:
        body (CreditRequestRequest | Unset):
        body (CreditRequestRequest | Unset):
        body (CreditRequestRequest | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreditRequestResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: CreditRequestRequest
    | CreditRequestRequest
    | CreditRequestRequest
    | Unset = UNSET,
) -> Response[CreditRequestResponse]:
    """Request additional credits

     Sends an email to the configured admin asking for more credits.

    Args:
        body (CreditRequestRequest | Unset):
        body (CreditRequestRequest | Unset):
        body (CreditRequestRequest | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreditRequestResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: CreditRequestRequest
    | CreditRequestRequest
    | CreditRequestRequest
    | Unset = UNSET,
) -> CreditRequestResponse | None:
    """Request additional credits

     Sends an email to the configured admin asking for more credits.

    Args:
        body (CreditRequestRequest | Unset):
        body (CreditRequestRequest | Unset):
        body (CreditRequestRequest | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreditRequestResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
