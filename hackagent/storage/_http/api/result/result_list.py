from http import HTTPStatus
from typing import Any
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import UNSET, Response, Unset
from ..models import PaginatedResultList, ResultListEvaluationStatus, ResultListOrdering


def _get_kwargs(
    *,
    evaluation_status: ResultListEvaluationStatus | Unset = UNSET,
    goal_index: int | Unset = UNSET,
    include_traces: bool | Unset = UNSET,
    ordering: ResultListOrdering | Unset = UNSET,
    page: int | Unset = UNSET,
    page_size: int | Unset = UNSET,
    run: UUID | Unset = UNSET,
    run_organization: UUID | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_evaluation_status: str | Unset = UNSET
    if not isinstance(evaluation_status, Unset):
        json_evaluation_status = evaluation_status.value

    params["evaluation_status"] = json_evaluation_status

    params["goal_index"] = goal_index

    params["include_traces"] = include_traces

    json_ordering: str | Unset = UNSET
    if not isinstance(ordering, Unset):
        json_ordering = ordering.value

    params["ordering"] = json_ordering

    params["page"] = page

    params["page_size"] = page_size

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
    evaluation_status: ResultListEvaluationStatus | Unset = UNSET,
    goal_index: int | Unset = UNSET,
    include_traces: bool | Unset = UNSET,
    ordering: ResultListOrdering | Unset = UNSET,
    page: int | Unset = UNSET,
    page_size: int | Unset = UNSET,
    run: UUID | Unset = UNSET,
    run_organization: UUID | Unset = UNSET,
) -> Response[PaginatedResultList]:
    """ViewSet for managing Result instances. Allows creation of Traces via an action.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    login token (Auth0 or Keycloak) authentication is supported for web dashboard use.
    Results are typically consumed by SDK for test result retrieval and analysis.

    Args:
        evaluation_status (ResultListEvaluationStatus | Unset):
        goal_index (int | Unset):
        include_traces (bool | Unset):
        ordering (ResultListOrdering | Unset):
        page (int | Unset):
        page_size (int | Unset):
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
        goal_index=goal_index,
        include_traces=include_traces,
        ordering=ordering,
        page=page,
        page_size=page_size,
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
    evaluation_status: ResultListEvaluationStatus | Unset = UNSET,
    goal_index: int | Unset = UNSET,
    include_traces: bool | Unset = UNSET,
    ordering: ResultListOrdering | Unset = UNSET,
    page: int | Unset = UNSET,
    page_size: int | Unset = UNSET,
    run: UUID | Unset = UNSET,
    run_organization: UUID | Unset = UNSET,
) -> PaginatedResultList | None:
    """ViewSet for managing Result instances. Allows creation of Traces via an action.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    login token (Auth0 or Keycloak) authentication is supported for web dashboard use.
    Results are typically consumed by SDK for test result retrieval and analysis.

    Args:
        evaluation_status (ResultListEvaluationStatus | Unset):
        goal_index (int | Unset):
        include_traces (bool | Unset):
        ordering (ResultListOrdering | Unset):
        page (int | Unset):
        page_size (int | Unset):
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
        goal_index=goal_index,
        include_traces=include_traces,
        ordering=ordering,
        page=page,
        page_size=page_size,
        run=run,
        run_organization=run_organization,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    evaluation_status: ResultListEvaluationStatus | Unset = UNSET,
    goal_index: int | Unset = UNSET,
    include_traces: bool | Unset = UNSET,
    ordering: ResultListOrdering | Unset = UNSET,
    page: int | Unset = UNSET,
    page_size: int | Unset = UNSET,
    run: UUID | Unset = UNSET,
    run_organization: UUID | Unset = UNSET,
) -> Response[PaginatedResultList]:
    """ViewSet for managing Result instances. Allows creation of Traces via an action.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    login token (Auth0 or Keycloak) authentication is supported for web dashboard use.
    Results are typically consumed by SDK for test result retrieval and analysis.

    Args:
        evaluation_status (ResultListEvaluationStatus | Unset):
        goal_index (int | Unset):
        include_traces (bool | Unset):
        ordering (ResultListOrdering | Unset):
        page (int | Unset):
        page_size (int | Unset):
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
        goal_index=goal_index,
        include_traces=include_traces,
        ordering=ordering,
        page=page,
        page_size=page_size,
        run=run,
        run_organization=run_organization,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    evaluation_status: ResultListEvaluationStatus | Unset = UNSET,
    goal_index: int | Unset = UNSET,
    include_traces: bool | Unset = UNSET,
    ordering: ResultListOrdering | Unset = UNSET,
    page: int | Unset = UNSET,
    page_size: int | Unset = UNSET,
    run: UUID | Unset = UNSET,
    run_organization: UUID | Unset = UNSET,
) -> PaginatedResultList | None:
    """ViewSet for managing Result instances. Allows creation of Traces via an action.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    login token (Auth0 or Keycloak) authentication is supported for web dashboard use.
    Results are typically consumed by SDK for test result retrieval and analysis.

    Args:
        evaluation_status (ResultListEvaluationStatus | Unset):
        goal_index (int | Unset):
        include_traces (bool | Unset):
        ordering (ResultListOrdering | Unset):
        page (int | Unset):
        page_size (int | Unset):
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
            goal_index=goal_index,
            include_traces=include_traces,
            ordering=ordering,
            page=page,
            page_size=page_size,
            run=run,
            run_organization=run_organization,
        )
    ).parsed
