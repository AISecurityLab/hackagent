---
sidebar_label: result_list
title: hackagent.server.api.result.result_list
---

#### sync\_detailed

```python
def sync_detailed(
        *,
        client: AuthenticatedClient,
        evaluation_status: ResultListEvaluationStatus | Unset = UNSET,
        page: int | Unset = UNSET,
        run: UUID | Unset = UNSET,
        run_organization: UUID | Unset = UNSET
) -> Response[PaginatedResultList]
```

ViewSet for managing Result instances. Allows creation of Traces via an action.

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
Auth0 authentication is supported as fallback for web dashboard use.
Results are typically consumed by SDK for test result retrieval and analysis.

**Arguments**:

  evaluation_status (ResultListEvaluationStatus | Unset):
  page (int | Unset):
  run (UUID | Unset):
  run_organization (UUID | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[PaginatedResultList]

#### sync

```python
def sync(*,
         client: AuthenticatedClient,
         evaluation_status: ResultListEvaluationStatus | Unset = UNSET,
         page: int | Unset = UNSET,
         run: UUID | Unset = UNSET,
         run_organization: UUID | Unset = UNSET) -> PaginatedResultList | None
```

ViewSet for managing Result instances. Allows creation of Traces via an action.

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
Auth0 authentication is supported as fallback for web dashboard use.
Results are typically consumed by SDK for test result retrieval and analysis.

**Arguments**:

  evaluation_status (ResultListEvaluationStatus | Unset):
  page (int | Unset):
  run (UUID | Unset):
  run_organization (UUID | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  PaginatedResultList

#### asyncio\_detailed

```python
async def asyncio_detailed(
        *,
        client: AuthenticatedClient,
        evaluation_status: ResultListEvaluationStatus | Unset = UNSET,
        page: int | Unset = UNSET,
        run: UUID | Unset = UNSET,
        run_organization: UUID | Unset = UNSET
) -> Response[PaginatedResultList]
```

ViewSet for managing Result instances. Allows creation of Traces via an action.

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
Auth0 authentication is supported as fallback for web dashboard use.
Results are typically consumed by SDK for test result retrieval and analysis.

**Arguments**:

  evaluation_status (ResultListEvaluationStatus | Unset):
  page (int | Unset):
  run (UUID | Unset):
  run_organization (UUID | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[PaginatedResultList]

#### asyncio

```python
async def asyncio(
        *,
        client: AuthenticatedClient,
        evaluation_status: ResultListEvaluationStatus | Unset = UNSET,
        page: int | Unset = UNSET,
        run: UUID | Unset = UNSET,
        run_organization: UUID | Unset = UNSET) -> PaginatedResultList | None
```

ViewSet for managing Result instances. Allows creation of Traces via an action.

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
Auth0 authentication is supported as fallback for web dashboard use.
Results are typically consumed by SDK for test result retrieval and analysis.

**Arguments**:

  evaluation_status (ResultListEvaluationStatus | Unset):
  page (int | Unset):
  run (UUID | Unset):
  run_organization (UUID | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  PaginatedResultList

