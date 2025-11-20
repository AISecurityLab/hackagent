from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.checkout_session_request_request import CheckoutSessionRequestRequest
from ...models.checkout_session_response import CheckoutSessionResponse
from ...models.generic_error_response import GenericErrorResponse
from ...types import Response


def _get_kwargs(
    *,
    body: Union[
        CheckoutSessionRequestRequest,
        CheckoutSessionRequestRequest,
        CheckoutSessionRequestRequest,
    ],
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/checkout/",
    }

    if isinstance(body, CheckoutSessionRequestRequest):
        _kwargs["json"] = body.to_dict()

        headers["Content-Type"] = "application/json"
    if isinstance(body, CheckoutSessionRequestRequest):
        _kwargs["data"] = body.to_dict()

        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if isinstance(body, CheckoutSessionRequestRequest):
        _kwargs["files"] = body.to_multipart()

        headers["Content-Type"] = "multipart/form-data"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[Union[CheckoutSessionResponse, GenericErrorResponse]]:
    if response.status_code == 200:
        response_200 = CheckoutSessionResponse.from_dict(response.json())

        return response_200
    if response.status_code == 400:
        response_400 = GenericErrorResponse.from_dict(response.json())

        return response_400
    if response.status_code == 404:
        response_404 = GenericErrorResponse.from_dict(response.json())

        return response_404
    if response.status_code == 500:
        response_500 = GenericErrorResponse.from_dict(response.json())

        return response_500
    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[Union[CheckoutSessionResponse, GenericErrorResponse]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: Union[
        CheckoutSessionRequestRequest,
        CheckoutSessionRequestRequest,
        CheckoutSessionRequestRequest,
    ],
) -> Response[Union[CheckoutSessionResponse, GenericErrorResponse]]:
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
        Response[Union[CheckoutSessionResponse, GenericErrorResponse]]
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
    body: Union[
        CheckoutSessionRequestRequest,
        CheckoutSessionRequestRequest,
        CheckoutSessionRequestRequest,
    ],
) -> Optional[Union[CheckoutSessionResponse, GenericErrorResponse]]:
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
        Union[CheckoutSessionResponse, GenericErrorResponse]
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: Union[
        CheckoutSessionRequestRequest,
        CheckoutSessionRequestRequest,
        CheckoutSessionRequestRequest,
    ],
) -> Response[Union[CheckoutSessionResponse, GenericErrorResponse]]:
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
        Response[Union[CheckoutSessionResponse, GenericErrorResponse]]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: Union[
        CheckoutSessionRequestRequest,
        CheckoutSessionRequestRequest,
        CheckoutSessionRequestRequest,
    ],
) -> Optional[Union[CheckoutSessionResponse, GenericErrorResponse]]:
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
        Union[CheckoutSessionResponse, GenericErrorResponse]
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
