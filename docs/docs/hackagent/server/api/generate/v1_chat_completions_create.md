---
sidebar_label: v1_chat_completions_create
title: hackagent.server.api.generate.v1_chat_completions_create
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

Generate text using AI Provider (OpenAI-compatible)

OpenAI-compatible chat completions endpoint.

Available at: /v1/chat/completions

Handles POST requests to generate text via a configured AI provider.
The request body follows OpenAI&#x27;s chat completions format.
The &#x27;model&#x27; field will be overridden by the server-configured generator model ID.
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

Generate text using AI Provider (OpenAI-compatible)

OpenAI-compatible chat completions endpoint.

Available at: /v1/chat/completions

Handles POST requests to generate text via a configured AI provider.
The request body follows OpenAI&#x27;s chat completions format.
The &#x27;model&#x27; field will be overridden by the server-configured generator model ID.
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

Generate text using AI Provider (OpenAI-compatible)

OpenAI-compatible chat completions endpoint.

Available at: /v1/chat/completions

Handles POST requests to generate text via a configured AI provider.
The request body follows OpenAI&#x27;s chat completions format.
The &#x27;model&#x27; field will be overridden by the server-configured generator model ID.
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

Generate text using AI Provider (OpenAI-compatible)

OpenAI-compatible chat completions endpoint.

Available at: /v1/chat/completions

Handles POST requests to generate text via a configured AI provider.
The request body follows OpenAI&#x27;s chat completions format.
The &#x27;model&#x27; field will be overridden by the server-configured generator model ID.
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

**Arguments**:

  body (GenerateRequestRequest):
  body (GenerateRequestRequest):
  body (GenerateRequestRequest):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  GenerateErrorResponse | GenerateSuccessResponse

