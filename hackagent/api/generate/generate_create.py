from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import UNSET, Response, Unset
from ..models import (
    GenerateErrorResponse,
    GenerateRequestRequest,
    GenerateSuccessResponse,
)


def _get_kwargs(
    *,
    body: GenerateRequestRequest
    | GenerateRequestRequest
    | GenerateRequestRequest
    | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/chat/completions",
    }

    if isinstance(body, GenerateRequestRequest):
        _kwargs["json"] = body.model_dump(by_alias=True, mode="json", exclude_none=True)

        headers["Content-Type"] = "application/json"
    if isinstance(body, GenerateRequestRequest):
        _kwargs["data"] = body.model_dump(by_alias=True, mode="json", exclude_none=True)

        headers["Content-Type"] = "application/x-www-form-urlencoded"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> GenerateErrorResponse | GenerateSuccessResponse | None:
    if response.status_code == 200:
        response_200 = GenerateSuccessResponse.model_validate(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = GenerateErrorResponse.model_validate(response.json())

        return response_400

    if response.status_code == 402:
        response_402 = GenerateErrorResponse.model_validate(response.json())

        return response_402

    if response.status_code == 403:
        response_403 = GenerateErrorResponse.model_validate(response.json())

        return response_403

    if response.status_code == 500:
        response_500 = GenerateErrorResponse.model_validate(response.json())

        return response_500

    if response.status_code == 502:
        response_502 = GenerateErrorResponse.model_validate(response.json())

        return response_502

    if response.status_code == 504:
        response_504 = GenerateErrorResponse.model_validate(response.json())

        return response_504

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[GenerateErrorResponse | GenerateSuccessResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: GenerateRequestRequest
    | GenerateRequestRequest
    | GenerateRequestRequest
    | Unset = UNSET,
) -> Response[GenerateErrorResponse | GenerateSuccessResponse]:
    r"""Generate text using AI Provider (OpenAI-compatible)

     OpenAI-compatible chat completions endpoint.

    Available at: /v1/chat/completions

    Handles POST requests to generate text via a configured AI provider.
    The request body follows OpenAI's chat completions format.
    The 'model' field will be overridden by the server-configured generator model ID.
    Billing and logging are handled internally.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    This is a core SDK operation for AI model generation in security tests.

    Compatible with OpenAI Python SDK:
    ```python
    from openai import OpenAI
    client = OpenAI(
        api_key=\"your_hackagent_api_key\",
        base_url=\"https://api.hackagent.dev\"
    )
    response = client.chat.completions.create(
        model=\"any\",  # Will be overridden by server
        messages=[{\"role\": \"user\", \"content\": \"Hello!\"}]
    )
    ```

    Args:
        body (GenerateRequestRequest):
        body (GenerateRequestRequest):
        body (GenerateRequestRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GenerateErrorResponse | GenerateSuccessResponse]
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
    body: GenerateRequestRequest
    | GenerateRequestRequest
    | GenerateRequestRequest
    | Unset = UNSET,
) -> GenerateErrorResponse | GenerateSuccessResponse | None:
    r"""Generate text using AI Provider (OpenAI-compatible)

     OpenAI-compatible chat completions endpoint.

    Available at: /v1/chat/completions

    Handles POST requests to generate text via a configured AI provider.
    The request body follows OpenAI's chat completions format.
    The 'model' field will be overridden by the server-configured generator model ID.
    Billing and logging are handled internally.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    This is a core SDK operation for AI model generation in security tests.

    Compatible with OpenAI Python SDK:
    ```python
    from openai import OpenAI
    client = OpenAI(
        api_key=\"your_hackagent_api_key\",
        base_url=\"https://api.hackagent.dev\"
    )
    response = client.chat.completions.create(
        model=\"any\",  # Will be overridden by server
        messages=[{\"role\": \"user\", \"content\": \"Hello!\"}]
    )
    ```

    Args:
        body (GenerateRequestRequest):
        body (GenerateRequestRequest):
        body (GenerateRequestRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GenerateErrorResponse | GenerateSuccessResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: GenerateRequestRequest
    | GenerateRequestRequest
    | GenerateRequestRequest
    | Unset = UNSET,
) -> Response[GenerateErrorResponse | GenerateSuccessResponse]:
    r"""Generate text using AI Provider (OpenAI-compatible)

     OpenAI-compatible chat completions endpoint.

    Available at: /v1/chat/completions

    Handles POST requests to generate text via a configured AI provider.
    The request body follows OpenAI's chat completions format.
    The 'model' field will be overridden by the server-configured generator model ID.
    Billing and logging are handled internally.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    This is a core SDK operation for AI model generation in security tests.

    Compatible with OpenAI Python SDK:
    ```python
    from openai import OpenAI
    client = OpenAI(
        api_key=\"your_hackagent_api_key\",
        base_url=\"https://api.hackagent.dev\"
    )
    response = client.chat.completions.create(
        model=\"any\",  # Will be overridden by server
        messages=[{\"role\": \"user\", \"content\": \"Hello!\"}]
    )
    ```

    Args:
        body (GenerateRequestRequest):
        body (GenerateRequestRequest):
        body (GenerateRequestRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GenerateErrorResponse | GenerateSuccessResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: GenerateRequestRequest
    | GenerateRequestRequest
    | GenerateRequestRequest
    | Unset = UNSET,
) -> GenerateErrorResponse | GenerateSuccessResponse | None:
    r"""Generate text using AI Provider (OpenAI-compatible)

     OpenAI-compatible chat completions endpoint.

    Available at: /v1/chat/completions

    Handles POST requests to generate text via a configured AI provider.
    The request body follows OpenAI's chat completions format.
    The 'model' field will be overridden by the server-configured generator model ID.
    Billing and logging are handled internally.

    SDK-primary endpoint - API Key authentication is recommended for programmatic access.
    This is a core SDK operation for AI model generation in security tests.

    Compatible with OpenAI Python SDK:
    ```python
    from openai import OpenAI
    client = OpenAI(
        api_key=\"your_hackagent_api_key\",
        base_url=\"https://api.hackagent.dev\"
    )
    response = client.chat.completions.create(
        model=\"any\",  # Will be overridden by server
        messages=[{\"role\": \"user\", \"content\": \"Hello!\"}]
    )
    ```

    Args:
        body (GenerateRequestRequest):
        body (GenerateRequestRequest):
        body (GenerateRequestRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GenerateErrorResponse | GenerateSuccessResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
