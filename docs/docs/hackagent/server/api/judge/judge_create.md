---
sidebar_label: judge_create
title: hackagent.server.api.judge.judge_create
---

#### sync\_detailed

```python
def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: GenerateRequestRequest
    | GenerateRequestRequest
    | GenerateRequestRequest
    | Unset = UNSET
) -> Response[GenerateErrorResponse | GenerateSuccessResponse]
```

Judge text or assess content using an AI Provider

Handles POST requests to assess or judge content via a configured Judge AI provider.
The request body should match the AI provider&#x27;s expected format (e.g. chat completions),
though the &#x27;model&#x27; field will be overridden by the server-configured judge model ID.
Billing and logging are handled internally.

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
This is a core SDK operation for AI-based evaluation in security tests.

**Arguments**:

  body (GenerateRequestRequest):
  body (GenerateRequestRequest):
  body (GenerateRequestRequest):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[GenerateErrorResponse | GenerateSuccessResponse]

#### sync

```python
def sync(
    *,
    client: AuthenticatedClient,
    body: GenerateRequestRequest
    | GenerateRequestRequest
    | GenerateRequestRequest
    | Unset = UNSET
) -> GenerateErrorResponse | GenerateSuccessResponse | None
```

Judge text or assess content using an AI Provider

Handles POST requests to assess or judge content via a configured Judge AI provider.
The request body should match the AI provider&#x27;s expected format (e.g. chat completions),
though the &#x27;model&#x27; field will be overridden by the server-configured judge model ID.
Billing and logging are handled internally.

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
This is a core SDK operation for AI-based evaluation in security tests.

**Arguments**:

  body (GenerateRequestRequest):
  body (GenerateRequestRequest):
  body (GenerateRequestRequest):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  GenerateErrorResponse | GenerateSuccessResponse

#### asyncio\_detailed

```python
async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: GenerateRequestRequest
    | GenerateRequestRequest
    | GenerateRequestRequest
    | Unset = UNSET
) -> Response[GenerateErrorResponse | GenerateSuccessResponse]
```

Judge text or assess content using an AI Provider

Handles POST requests to assess or judge content via a configured Judge AI provider.
The request body should match the AI provider&#x27;s expected format (e.g. chat completions),
though the &#x27;model&#x27; field will be overridden by the server-configured judge model ID.
Billing and logging are handled internally.

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
This is a core SDK operation for AI-based evaluation in security tests.

**Arguments**:

  body (GenerateRequestRequest):
  body (GenerateRequestRequest):
  body (GenerateRequestRequest):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[GenerateErrorResponse | GenerateSuccessResponse]

#### asyncio

```python
async def asyncio(
    *,
    client: AuthenticatedClient,
    body: GenerateRequestRequest
    | GenerateRequestRequest
    | GenerateRequestRequest
    | Unset = UNSET
) -> GenerateErrorResponse | GenerateSuccessResponse | None
```

Judge text or assess content using an AI Provider

Handles POST requests to assess or judge content via a configured Judge AI provider.
The request body should match the AI provider&#x27;s expected format (e.g. chat completions),
though the &#x27;model&#x27; field will be overridden by the server-configured judge model ID.
Billing and logging are handled internally.

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
This is a core SDK operation for AI-based evaluation in security tests.

**Arguments**:

  body (GenerateRequestRequest):
  body (GenerateRequestRequest):
  body (GenerateRequestRequest):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  GenerateErrorResponse | GenerateSuccessResponse

