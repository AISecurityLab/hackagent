from http import HTTPStatus
from typing import Any
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import UNSET, Response, Unset
from ..models import PaginatedResultList, EvaluationStatusEnum


def _get_kwargs(
    *,
    evaluation_status: EvaluationStatusEnum | Unset = UNSET,
    page: int | Unset = UNSET,
    prompt: UUID | Unset = UNSET,
    run: UUID | Unset = UNSET,
    run_organization: UUID | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_evaluation_status: str | Unset = UNSET
    if not isinstance(evaluation_status, Unset):
        json_evaluation_status = evaluation_status.value

    params["evaluation_status"] = json_evaluation_status

    params["page"] = page

    json_prompt: str | Unset = UNSET
    if not isinstance(prompt, Unset):
        json_prompt = str(prompt)
    params["prompt"] = json_prompt

    json_run: str | Unset = UNSET
    if not isinstance(run, Unset):
        json_run = str(run)
    params["run"] = json_run

    json_run_organization: str | Unset = UNSET
    if not isinstance(run_organization, Unset):
        json_run_organization = str(run_organization)
    params["run__organization"] = json_run_organization

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/result",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> PaginatedResultList | None:
    if response.status_code == 200:
        response_200 = PaginatedResultList.model_validate(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[PaginatedResultList]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    evaluation_status: EvaluationStatusEnum | Unset = UNSET,
    page: int | Unset = UNSET,
    prompt: UUID | Unset = UNSET,
    run: UUID | Unset = UNSET,
    run_organization: UUID | Unset = UNSET,
) -> Response[PaginatedResultList]:
    """ViewSet for managing Result instances. Allows creation of Traces via an action.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Auth0 authentication is supported as fallback for web dashboard use.
    Results are typically consumed by SDK for test result retrieval and analysis.

    Args:
        evaluation_status (EvaluationStatusEnum | Unset):
        page (int | Unset):
        prompt (UUID | Unset):
        run (UUID | Unset):
        run_organization (UUID | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[PaginatedResultList]
    """

    kwargs = _get_kwargs(
        evaluation_status=evaluation_status,
        page=page,
        prompt=prompt,
        run=run,
        run_organization=run_organization,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    evaluation_status: EvaluationStatusEnum | Unset = UNSET,
    page: int | Unset = UNSET,
    prompt: UUID | Unset = UNSET,
    run: UUID | Unset = UNSET,
    run_organization: UUID | Unset = UNSET,
) -> PaginatedResultList | None:
    """ViewSet for managing Result instances. Allows creation of Traces via an action.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Auth0 authentication is supported as fallback for web dashboard use.
    Results are typically consumed by SDK for test result retrieval and analysis.

    Args:
        evaluation_status (EvaluationStatusEnum | Unset):
        page (int | Unset):
        prompt (UUID | Unset):
        run (UUID | Unset):
        run_organization (UUID | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        PaginatedResultList
    """

    return sync_detailed(
        client=client,
        evaluation_status=evaluation_status,
        page=page,
        prompt=prompt,
        run=run,
        run_organization=run_organization,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    evaluation_status: EvaluationStatusEnum | Unset = UNSET,
    page: int | Unset = UNSET,
    prompt: UUID | Unset = UNSET,
    run: UUID | Unset = UNSET,
    run_organization: UUID | Unset = UNSET,
) -> Response[PaginatedResultList]:
    """ViewSet for managing Result instances. Allows creation of Traces via an action.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Auth0 authentication is supported as fallback for web dashboard use.
    Results are typically consumed by SDK for test result retrieval and analysis.

    Args:
        evaluation_status (EvaluationStatusEnum | Unset):
        page (int | Unset):
        prompt (UUID | Unset):
        run (UUID | Unset):
        run_organization (UUID | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[PaginatedResultList]
    """

    kwargs = _get_kwargs(
        evaluation_status=evaluation_status,
        page=page,
        prompt=prompt,
        run=run,
        run_organization=run_organization,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    evaluation_status: EvaluationStatusEnum | Unset = UNSET,
    page: int | Unset = UNSET,
    prompt: UUID | Unset = UNSET,
    run: UUID | Unset = UNSET,
    run_organization: UUID | Unset = UNSET,
) -> PaginatedResultList | None:
    """ViewSet for managing Result instances. Allows creation of Traces via an action.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    Auth0 authentication is supported as fallback for web dashboard use.
    Results are typically consumed by SDK for test result retrieval and analysis.

    Args:
        evaluation_status (EvaluationStatusEnum | Unset):
        page (int | Unset):
        prompt (UUID | Unset):
        run (UUID | Unset):
        run_organization (UUID | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        PaginatedResultList
    """

    return (
        await asyncio_detailed(
            client=client,
            evaluation_status=evaluation_status,
            page=page,
            prompt=prompt,
            run=run,
            run_organization=run_organization,
        )
    ).parsed
