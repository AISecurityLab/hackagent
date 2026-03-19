---
sidebar_label: key_retrieve
title: hackagent.server.api.key.key_retrieve
---

#### sync\_detailed

```python
def sync_detailed(prefix: str, *,
                  client: AuthenticatedClient) -> Response[UserAPIKey]
```

ViewSet for managing User API Keys.

Web-only endpoint - requires Auth0 authentication.
API keys cannot manage other API keys for security reasons.

**Arguments**:

  prefix (str):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[UserAPIKey]

#### sync

```python
def sync(prefix: str, *, client: AuthenticatedClient) -> UserAPIKey | None
```

ViewSet for managing User API Keys.

Web-only endpoint - requires Auth0 authentication.
API keys cannot manage other API keys for security reasons.

**Arguments**:

  prefix (str):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  UserAPIKey

#### asyncio\_detailed

```python
async def asyncio_detailed(
        prefix: str, *, client: AuthenticatedClient) -> Response[UserAPIKey]
```

ViewSet for managing User API Keys.

Web-only endpoint - requires Auth0 authentication.
API keys cannot manage other API keys for security reasons.

**Arguments**:

  prefix (str):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[UserAPIKey]

#### asyncio

```python
async def asyncio(prefix: str, *,
                  client: AuthenticatedClient) -> UserAPIKey | None
```

ViewSet for managing User API Keys.

Web-only endpoint - requires Auth0 authentication.
API keys cannot manage other API keys for security reasons.

**Arguments**:

  prefix (str):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  UserAPIKey

