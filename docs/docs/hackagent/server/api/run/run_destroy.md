---
sidebar_label: run_destroy
title: hackagent.server.api.run.run_destroy
---

#### sync\_detailed

```python
def sync_detailed(id: UUID, *, client: AuthenticatedClient) -> Response[Any]
```

ViewSet for managing Run instances.
Primarily for listing/retrieving runs.
Creation of server-side runs is handled by custom actions.
Runs initiated from Attack definitions are created via AttackViewSet.

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
Auth0 authentication is supported as fallback for web dashboard use.
This is a core SDK operation for executing and monitoring security tests.

**Arguments**:

  id (UUID):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[Any]

#### asyncio\_detailed

```python
async def asyncio_detailed(id: UUID, *,
                           client: AuthenticatedClient) -> Response[Any]
```

ViewSet for managing Run instances.
Primarily for listing/retrieving runs.
Creation of server-side runs is handled by custom actions.
Runs initiated from Attack definitions are created via AttackViewSet.

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
Auth0 authentication is supported as fallback for web dashboard use.
This is a core SDK operation for executing and monitoring security tests.

**Arguments**:

  id (UUID):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[Any]

