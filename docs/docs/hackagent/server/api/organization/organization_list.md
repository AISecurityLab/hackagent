---
sidebar_label: organization_list
title: hackagent.server.api.organization.organization_list
---

#### sync\_detailed

```python
def sync_detailed(
        *,
        client: AuthenticatedClient,
        page: int | Unset = UNSET) -> Response[PaginatedOrganizationList]
```

Provides access to Organization details for the authenticated user.

Web-only endpoint - requires Auth0 authentication.
Organization management and billing operations require browser context.

**Arguments**:

  page (int | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[PaginatedOrganizationList]

#### sync

```python
def sync(*,
         client: AuthenticatedClient,
         page: int | Unset = UNSET) -> PaginatedOrganizationList | None
```

Provides access to Organization details for the authenticated user.

Web-only endpoint - requires Auth0 authentication.
Organization management and billing operations require browser context.

**Arguments**:

  page (int | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  PaginatedOrganizationList

#### asyncio\_detailed

```python
async def asyncio_detailed(
        *,
        client: AuthenticatedClient,
        page: int | Unset = UNSET) -> Response[PaginatedOrganizationList]
```

Provides access to Organization details for the authenticated user.

Web-only endpoint - requires Auth0 authentication.
Organization management and billing operations require browser context.

**Arguments**:

  page (int | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[PaginatedOrganizationList]

#### asyncio

```python
async def asyncio(
        *,
        client: AuthenticatedClient,
        page: int | Unset = UNSET) -> PaginatedOrganizationList | None
```

Provides access to Organization details for the authenticated user.

Web-only endpoint - requires Auth0 authentication.
Organization management and billing operations require browser context.

**Arguments**:

  page (int | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  PaginatedOrganizationList

