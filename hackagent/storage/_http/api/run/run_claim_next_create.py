from http import HTTPStatus
from typing import Any, cast

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import UNSET, Response, Unset
from ..models import ClaimedRun, ClaimRequest


def _get_kwargs(
    *,
    body: ClaimRequest | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/run/claim-next",
    }

    if not isinstance(body, Unset):
        _kwargs["json"] = body.model_dump(mode="json", exclude_unset=True)

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Any | ClaimedRun | None:
    if response.status_code == 200:
        response_200 = ClaimedRun.model_validate(response.json())

        return response_200

    if response.status_code == 204:
        response_204 = cast(Any, None)
        return response_204

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Any | ClaimedRun]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: ClaimRequest | Unset = UNSET,
) -> Response[Any | ClaimedRun]:
    """Claims the oldest queued cloud campaign run of an organization below
    its concurrent cloud run limit (worker token only), as ``claim``
    does. Runs whose secrets are gone fail and are skipped. 204 when no
    run can be claimed.

    Args:
        body (ClaimRequest | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | ClaimedRun]
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
    body: ClaimRequest | Unset = UNSET,
) -> Any | ClaimedRun | None:
    """Claims the oldest queued cloud campaign run of an organization below
    its concurrent cloud run limit (worker token only), as ``claim``
    does. Runs whose secrets are gone fail and are skipped. 204 when no
    run can be claimed.

    Args:
        body (ClaimRequest | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | ClaimedRun
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: ClaimRequest | Unset = UNSET,
) -> Response[Any | ClaimedRun]:
    """Claims the oldest queued cloud campaign run of an organization below
    its concurrent cloud run limit (worker token only), as ``claim``
    does. Runs whose secrets are gone fail and are skipped. 204 when no
    run can be claimed.

    Args:
        body (ClaimRequest | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | ClaimedRun]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: ClaimRequest | Unset = UNSET,
) -> Any | ClaimedRun | None:
    """Claims the oldest queued cloud campaign run of an organization below
    its concurrent cloud run limit (worker token only), as ``claim``
    does. Runs whose secrets are gone fail and are skipped. 204 when no
    run can be claimed.

    Args:
        body (ClaimRequest | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | ClaimedRun
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
