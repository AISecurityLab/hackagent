---
sidebar_label: organization_destroy
title: hackagent.server.api.organization.organization_destroy
---

#### sync\_detailed

```python
def sync_detailed(id: UUID, *, client: AuthenticatedClient) -> Response[Any]
```

Provides access to Organization details for the authenticated user.

Web-only endpoint - requires Auth0 authentication.
Organization management and billing operations require browser context.

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

Provides access to Organization details for the authenticated user.

Web-only endpoint - requires Auth0 authentication.
Organization management and billing operations require browser context.

**Arguments**:

  id (UUID):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[Any]

