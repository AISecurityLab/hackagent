---
sidebar_label: run_list
title: hackagent.server.api.run.run_list
---

#### sync\_detailed

```python
def sync_detailed(
        *,
        client: AuthenticatedClient,
        agent: UUID | Unset = UNSET,
        attack: UUID | Unset = UNSET,
        is_client_executed: bool | Unset = UNSET,
        organization: UUID | Unset = UNSET,
        page: int | Unset = UNSET,
        page_size: int | Unset = UNSET,
        status: RunListStatus | Unset = UNSET) -> Response[PaginatedRunList]
```

ViewSet for managing Run instances.
Primarily for listing/retrieving runs.
Creation of server-side runs is handled by custom actions.
Runs initiated from Attack definitions are created via AttackViewSet.

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
Auth0 authentication is supported as fallback for web dashboard use.
This is a core SDK operation for executing and monitoring security tests.

**Arguments**:

  agent (UUID | Unset):
  attack (UUID | Unset):
  is_client_executed (bool | Unset):
  organization (UUID | Unset):
  page (int | Unset):
  page_size (int | Unset):
  status (RunListStatus | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[PaginatedRunList]

#### sync

```python
def sync(*,
         client: AuthenticatedClient,
         agent: UUID | Unset = UNSET,
         attack: UUID | Unset = UNSET,
         is_client_executed: bool | Unset = UNSET,
         organization: UUID | Unset = UNSET,
         page: int | Unset = UNSET,
         page_size: int | Unset = UNSET,
         status: RunListStatus | Unset = UNSET) -> PaginatedRunList | None
```

ViewSet for managing Run instances.
Primarily for listing/retrieving runs.
Creation of server-side runs is handled by custom actions.
Runs initiated from Attack definitions are created via AttackViewSet.

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
Auth0 authentication is supported as fallback for web dashboard use.
This is a core SDK operation for executing and monitoring security tests.

**Arguments**:

  agent (UUID | Unset):
  attack (UUID | Unset):
  is_client_executed (bool | Unset):
  organization (UUID | Unset):
  page (int | Unset):
  page_size (int | Unset):
  status (RunListStatus | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  PaginatedRunList

#### asyncio\_detailed

```python
async def asyncio_detailed(
        *,
        client: AuthenticatedClient,
        agent: UUID | Unset = UNSET,
        attack: UUID | Unset = UNSET,
        is_client_executed: bool | Unset = UNSET,
        organization: UUID | Unset = UNSET,
        page: int | Unset = UNSET,
        page_size: int | Unset = UNSET,
        status: RunListStatus | Unset = UNSET) -> Response[PaginatedRunList]
```

ViewSet for managing Run instances.
Primarily for listing/retrieving runs.
Creation of server-side runs is handled by custom actions.
Runs initiated from Attack definitions are created via AttackViewSet.

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
Auth0 authentication is supported as fallback for web dashboard use.
This is a core SDK operation for executing and monitoring security tests.

**Arguments**:

  agent (UUID | Unset):
  attack (UUID | Unset):
  is_client_executed (bool | Unset):
  organization (UUID | Unset):
  page (int | Unset):
  page_size (int | Unset):
  status (RunListStatus | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[PaginatedRunList]

#### asyncio

```python
async def asyncio(
        *,
        client: AuthenticatedClient,
        agent: UUID | Unset = UNSET,
        attack: UUID | Unset = UNSET,
        is_client_executed: bool | Unset = UNSET,
        organization: UUID | Unset = UNSET,
        page: int | Unset = UNSET,
        page_size: int | Unset = UNSET,
        status: RunListStatus | Unset = UNSET) -> PaginatedRunList | None
```

ViewSet for managing Run instances.
Primarily for listing/retrieving runs.
Creation of server-side runs is handled by custom actions.
Runs initiated from Attack definitions are created via AttackViewSet.

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
Auth0 authentication is supported as fallback for web dashboard use.
This is a core SDK operation for executing and monitoring security tests.

**Arguments**:

  agent (UUID | Unset):
  attack (UUID | Unset):
  is_client_executed (bool | Unset):
  organization (UUID | Unset):
  page (int | Unset):
  page_size (int | Unset):
  status (RunListStatus | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  PaginatedRunList

