---
sidebar_label: key_list
title: hackagent.server.api.key.key_list
---

#### sync\_detailed

```python
def sync_detailed(
        *,
        client: AuthenticatedClient,
        page: int | Unset = UNSET) -> Response[PaginatedUserAPIKeyList]
```

ViewSet for managing User API Keys.

Web-only endpoint - requires Auth0 authentication.
API keys cannot manage other API keys for security reasons.

**Arguments**:

  page (int | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[PaginatedUserAPIKeyList]

#### sync

```python
def sync(*,
         client: AuthenticatedClient,
         page: int | Unset = UNSET) -> PaginatedUserAPIKeyList | None
```

ViewSet for managing User API Keys.

Web-only endpoint - requires Auth0 authentication.
API keys cannot manage other API keys for security reasons.

**Arguments**:

  page (int | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  PaginatedUserAPIKeyList

#### asyncio\_detailed

```python
async def asyncio_detailed(
        *,
        client: AuthenticatedClient,
        page: int | Unset = UNSET) -> Response[PaginatedUserAPIKeyList]
```

ViewSet for managing User API Keys.

Web-only endpoint - requires Auth0 authentication.
API keys cannot manage other API keys for security reasons.

**Arguments**:

  page (int | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[PaginatedUserAPIKeyList]

#### asyncio

```python
async def asyncio(*,
                  client: AuthenticatedClient,
                  page: int | Unset = UNSET) -> PaginatedUserAPIKeyList | None
```

ViewSet for managing User API Keys.

Web-only endpoint - requires Auth0 authentication.
API keys cannot manage other API keys for security reasons.

**Arguments**:

  page (int | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  PaginatedUserAPIKeyList

