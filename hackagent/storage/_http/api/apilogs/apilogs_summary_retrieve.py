import datetime
from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import UNSET, Response, Unset
from ..models import APITokenLog


def _get_kwargs(
    *,
    by_key: bool | Unset = UNSET,
    end_date: datetime.date,
    start_date: datetime.date,
    tz: str | Unset = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    params["by_key"] = by_key

    json_end_date = end_date.isoformat()
    params["end_date"] = json_end_date

    json_start_date = start_date.isoformat()
    params["start_date"] = json_start_date

    params["tz"] = tz

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/apilogs/summary",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> APITokenLog | None:
    if response.status_code == 200:
        response_200 = APITokenLog.model_validate(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[APITokenLog]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    by_key: bool | Unset = UNSET,
    end_date: datetime.date,
    start_date: datetime.date,
    tz: str | Unset = UNSET,
) -> Response[APITokenLog]:
    """Provides read-only access to APITokenLog entries for the user's organization.

    Web-only endpoint - requires Auth0 authentication.
    Usage logs are intended for web dashboard monitoring.

    Args:
        by_key (bool | Unset):
        end_date (datetime.date):
        start_date (datetime.date):
        tz (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[APITokenLog]
    """

    kwargs = _get_kwargs(
        by_key=by_key,
        end_date=end_date,
        start_date=start_date,
        tz=tz,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    by_key: bool | Unset = UNSET,
    end_date: datetime.date,
    start_date: datetime.date,
    tz: str | Unset = UNSET,
) -> APITokenLog | None:
    """Provides read-only access to APITokenLog entries for the user's organization.

    Web-only endpoint - requires Auth0 authentication.
    Usage logs are intended for web dashboard monitoring.

    Args:
        by_key (bool | Unset):
        end_date (datetime.date):
        start_date (datetime.date):
        tz (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        APITokenLog
    """

    return sync_detailed(
        client=client,
        by_key=by_key,
        end_date=end_date,
        start_date=start_date,
        tz=tz,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    by_key: bool | Unset = UNSET,
    end_date: datetime.date,
    start_date: datetime.date,
    tz: str | Unset = UNSET,
) -> Response[APITokenLog]:
    """Provides read-only access to APITokenLog entries for the user's organization.

    Web-only endpoint - requires Auth0 authentication.
    Usage logs are intended for web dashboard monitoring.

    Args:
        by_key (bool | Unset):
        end_date (datetime.date):
        start_date (datetime.date):
        tz (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[APITokenLog]
    """

    kwargs = _get_kwargs(
        by_key=by_key,
        end_date=end_date,
        start_date=start_date,
        tz=tz,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    by_key: bool | Unset = UNSET,
    end_date: datetime.date,
    start_date: datetime.date,
    tz: str | Unset = UNSET,
) -> APITokenLog | None:
    """Provides read-only access to APITokenLog entries for the user's organization.

    Web-only endpoint - requires Auth0 authentication.
    Usage logs are intended for web dashboard monitoring.

    Args:
        by_key (bool | Unset):
        end_date (datetime.date):
        start_date (datetime.date):
        tz (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        APITokenLog
    """

    return (
        await asyncio_detailed(
            client=client,
            by_key=by_key,
            end_date=end_date,
            start_date=start_date,
            tz=tz,
        )
    ).parsed
