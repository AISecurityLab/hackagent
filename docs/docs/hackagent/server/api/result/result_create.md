---
sidebar_label: result_create
title: hackagent.server.api.result.result_create
---

#### sync\_detailed

```python
def sync_detailed(*, client: AuthenticatedClient,
                  body: ResultRequest) -> Response[Result]
```

ViewSet for managing Result instances. Allows creation of Traces via an action.

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
Auth0 authentication is supported as fallback for web dashboard use.
Results are typically consumed by SDK for test result retrieval and analysis.

**Arguments**:

- `body` _ResultRequest_ - Serializer for the Result model, often nested in RunSerializer.
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[Result]

#### sync

```python
def sync(*, client: AuthenticatedClient, body: ResultRequest) -> Result | None
```

ViewSet for managing Result instances. Allows creation of Traces via an action.

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
Auth0 authentication is supported as fallback for web dashboard use.
Results are typically consumed by SDK for test result retrieval and analysis.

**Arguments**:

- `body` _ResultRequest_ - Serializer for the Result model, often nested in RunSerializer.
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Result

#### asyncio\_detailed

```python
async def asyncio_detailed(*, client: AuthenticatedClient,
                           body: ResultRequest) -> Response[Result]
```

ViewSet for managing Result instances. Allows creation of Traces via an action.

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
Auth0 authentication is supported as fallback for web dashboard use.
Results are typically consumed by SDK for test result retrieval and analysis.

**Arguments**:

- `body` _ResultRequest_ - Serializer for the Result model, often nested in RunSerializer.
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[Result]

#### asyncio

```python
async def asyncio(*, client: AuthenticatedClient,
                  body: ResultRequest) -> Result | None
```

ViewSet for managing Result instances. Allows creation of Traces via an action.

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
Auth0 authentication is supported as fallback for web dashboard use.
Results are typically consumed by SDK for test result retrieval and analysis.

**Arguments**:

- `body` _ResultRequest_ - Serializer for the Result model, often nested in RunSerializer.
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Result

