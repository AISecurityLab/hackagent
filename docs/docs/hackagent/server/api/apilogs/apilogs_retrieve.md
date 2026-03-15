---
sidebar_label: apilogs_retrieve
title: hackagent.server.api.apilogs.apilogs_retrieve
---

#### sync\_detailed

```python
def sync_detailed(id: int, *,
                  client: AuthenticatedClient) -> Response[APITokenLog]
```

Provides read-only access to APITokenLog entries for the user&#x27;s organization.

Web-only endpoint - requires Auth0 authentication.
Usage logs are intended for web dashboard monitoring.

**Arguments**:

  id (int):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[APITokenLog]

#### sync

```python
def sync(id: int, *, client: AuthenticatedClient) -> APITokenLog | None
```

Provides read-only access to APITokenLog entries for the user&#x27;s organization.

Web-only endpoint - requires Auth0 authentication.
Usage logs are intended for web dashboard monitoring.

**Arguments**:

  id (int):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  APITokenLog

#### asyncio\_detailed

```python
async def asyncio_detailed(
        id: int, *, client: AuthenticatedClient) -> Response[APITokenLog]
```

Provides read-only access to APITokenLog entries for the user&#x27;s organization.

Web-only endpoint - requires Auth0 authentication.
Usage logs are intended for web dashboard monitoring.

**Arguments**:

  id (int):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[APITokenLog]

#### asyncio

```python
async def asyncio(id: int, *,
                  client: AuthenticatedClient) -> APITokenLog | None
```

Provides read-only access to APITokenLog entries for the user&#x27;s organization.

Web-only endpoint - requires Auth0 authentication.
Usage logs are intended for web dashboard monitoring.

**Arguments**:

  id (int):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  APITokenLog

