from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import UNSET, Response, Unset
from ..models import (
    CheckoutSessionRequestRequest,
    CheckoutSessionResponse,
    GenericErrorResponse,
)


def _get_kwargs(
    *,
    body: CheckoutSessionRequestRequest
    | CheckoutSessionRequestRequest
    | CheckoutSessionRequestRequest
    | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/checkout/",
    }

    if isinstance(body, CheckoutSessionRequestRequest):
        _kwargs["json"] = body.model_dump(by_alias=True, mode="json", exclude_none=True)

        headers["Content-Type"] = "application/json"
    if isinstance(body, CheckoutSessionRequestRequest):
        _kwargs["data"] = body.model_dump(by_alias=True, mode="json", exclude_none=True)

        headers["Content-Type"] = "application/x-www-form-urlencoded"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> CheckoutSessionResponse | GenericErrorResponse | None:
    if response.status_code == 200:
        response_200 = CheckoutSessionResponse.model_validate(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = GenericErrorResponse.model_validate(response.json())

        return response_400

    if response.status_code == 404:
        response_404 = GenericErrorResponse.model_validate(response.json())

        return response_404

    if response.status_code == 500:
        response_500 = GenericErrorResponse.model_validate(response.json())

        return response_500

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[CheckoutSessionResponse | GenericErrorResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: CheckoutSessionRequestRequest
    | CheckoutSessionRequestRequest
    | CheckoutSessionRequestRequest
    | Unset = UNSET,
) -> Response[CheckoutSessionResponse | GenericErrorResponse]:
    """Create Stripe Checkout Session

     Initiates a Stripe Checkout session for purchasing API credits.
    The user must be authenticated.
    The number of credits to purchase must be provided in the request body.

    Args:
        body (CheckoutSessionRequestRequest):
        body (CheckoutSessionRequestRequest):
        body (CheckoutSessionRequestRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CheckoutSessionResponse | GenericErrorResponse]
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
    body: CheckoutSessionRequestRequest
    | CheckoutSessionRequestRequest
    | CheckoutSessionRequestRequest
    | Unset = UNSET,
) -> CheckoutSessionResponse | GenericErrorResponse | None:
    """Create Stripe Checkout Session

     Initiates a Stripe Checkout session for purchasing API credits.
    The user must be authenticated.
    The number of credits to purchase must be provided in the request body.

    Args:
        body (CheckoutSessionRequestRequest):
        body (CheckoutSessionRequestRequest):
        body (CheckoutSessionRequestRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CheckoutSessionResponse | GenericErrorResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: CheckoutSessionRequestRequest
    | CheckoutSessionRequestRequest
    | CheckoutSessionRequestRequest
    | Unset = UNSET,
) -> Response[CheckoutSessionResponse | GenericErrorResponse]:
    """Create Stripe Checkout Session

     Initiates a Stripe Checkout session for purchasing API credits.
    The user must be authenticated.
    The number of credits to purchase must be provided in the request body.

    Args:
        body (CheckoutSessionRequestRequest):
        body (CheckoutSessionRequestRequest):
        body (CheckoutSessionRequestRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CheckoutSessionResponse | GenericErrorResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: CheckoutSessionRequestRequest
    | CheckoutSessionRequestRequest
    | CheckoutSessionRequestRequest
    | Unset = UNSET,
) -> CheckoutSessionResponse | GenericErrorResponse | None:
    """Create Stripe Checkout Session

     Initiates a Stripe Checkout session for purchasing API credits.
    The user must be authenticated.
    The number of credits to purchase must be provided in the request body.

    Args:
        body (CheckoutSessionRequestRequest):
        body (CheckoutSessionRequestRequest):
        body (CheckoutSessionRequestRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CheckoutSessionResponse | GenericErrorResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
