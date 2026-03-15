---
sidebar_label: key_create
title: hackagent.server.api.key.key_create
---

#### sync\_detailed

```python
def sync_detailed(*, client: AuthenticatedClient,
                  body: UserAPIKeyRequest) -> Response[UserAPIKey]
```

ViewSet for managing User API Keys.

Web-only endpoint - requires Auth0 authentication.
API keys cannot manage other API keys for security reasons.

**Arguments**:

- `body` _UserAPIKeyRequest_ - Serializer for User API Keys.
  Exposes read-only information about the key, including its prefix.
  The full key is only shown once upon creation by the ViewSet.
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[UserAPIKey]

#### sync

```python
def sync(*, client: AuthenticatedClient,
         body: UserAPIKeyRequest) -> UserAPIKey | None
```

ViewSet for managing User API Keys.

Web-only endpoint - requires Auth0 authentication.
API keys cannot manage other API keys for security reasons.

**Arguments**:

- `body` _UserAPIKeyRequest_ - Serializer for User API Keys.
  Exposes read-only information about the key, including its prefix.
  The full key is only shown once upon creation by the ViewSet.
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  UserAPIKey

#### asyncio\_detailed

```python
async def asyncio_detailed(*, client: AuthenticatedClient,
                           body: UserAPIKeyRequest) -> Response[UserAPIKey]
```

ViewSet for managing User API Keys.

Web-only endpoint - requires Auth0 authentication.
API keys cannot manage other API keys for security reasons.

**Arguments**:

- `body` _UserAPIKeyRequest_ - Serializer for User API Keys.
  Exposes read-only information about the key, including its prefix.
  The full key is only shown once upon creation by the ViewSet.
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[UserAPIKey]

#### asyncio

```python
async def asyncio(*, client: AuthenticatedClient,
                  body: UserAPIKeyRequest) -> UserAPIKey | None
```

ViewSet for managing User API Keys.

Web-only endpoint - requires Auth0 authentication.
API keys cannot manage other API keys for security reasons.

**Arguments**:

- `body` _UserAPIKeyRequest_ - Serializer for User API Keys.
  Exposes read-only information about the key, including its prefix.
  The full key is only shown once upon creation by the ViewSet.
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  UserAPIKey

