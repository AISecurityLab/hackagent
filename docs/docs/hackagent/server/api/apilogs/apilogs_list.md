---
sidebar_label: apilogs_list
title: hackagent.server.api.apilogs.apilogs_list
---

#### sync\_detailed

```python
def sync_detailed(
        *,
        client: AuthenticatedClient,
        page: int | Unset = UNSET) -> Response[PaginatedAPITokenLogList]
```

Provides read-only access to APITokenLog entries for the user&#x27;s organization.

Web-only endpoint - requires Auth0 authentication.
Usage logs are intended for web dashboard monitoring.

**Arguments**:

  page (int | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[PaginatedAPITokenLogList]

#### sync

```python
def sync(*,
         client: AuthenticatedClient,
         page: int | Unset = UNSET) -> PaginatedAPITokenLogList | None
```

Provides read-only access to APITokenLog entries for the user&#x27;s organization.

Web-only endpoint - requires Auth0 authentication.
Usage logs are intended for web dashboard monitoring.

**Arguments**:

  page (int | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  PaginatedAPITokenLogList

#### asyncio\_detailed

```python
async def asyncio_detailed(
        *,
        client: AuthenticatedClient,
        page: int | Unset = UNSET) -> Response[PaginatedAPITokenLogList]
```

Provides read-only access to APITokenLog entries for the user&#x27;s organization.

Web-only endpoint - requires Auth0 authentication.
Usage logs are intended for web dashboard monitoring.

**Arguments**:

  page (int | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[PaginatedAPITokenLogList]

#### asyncio

```python
async def asyncio(
        *,
        client: AuthenticatedClient,
        page: int | Unset = UNSET) -> PaginatedAPITokenLogList | None
```

Provides read-only access to APITokenLog entries for the user&#x27;s organization.

Web-only endpoint - requires Auth0 authentication.
Usage logs are intended for web dashboard monitoring.

**Arguments**:

  page (int | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  PaginatedAPITokenLogList

