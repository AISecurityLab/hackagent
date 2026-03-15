---
sidebar_label: organization_create
title: hackagent.server.api.organization.organization_create
---

#### sync\_detailed

```python
def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: OrganizationRequest
    | OrganizationRequest
    | OrganizationRequest
    | Unset = UNSET
) -> Response[Organization]
```

Provides access to Organization details for the authenticated user.

Web-only endpoint - requires Auth0 authentication.
Organization management and billing operations require browser context.

**Arguments**:

  body (OrganizationRequest):
  body (OrganizationRequest):
  body (OrganizationRequest):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[Organization]

#### sync

```python
def sync(
    *,
    client: AuthenticatedClient,
    body: OrganizationRequest
    | OrganizationRequest
    | OrganizationRequest
    | Unset = UNSET
) -> Organization | None
```

Provides access to Organization details for the authenticated user.

Web-only endpoint - requires Auth0 authentication.
Organization management and billing operations require browser context.

**Arguments**:

  body (OrganizationRequest):
  body (OrganizationRequest):
  body (OrganizationRequest):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Organization

#### asyncio\_detailed

```python
async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: OrganizationRequest
    | OrganizationRequest
    | OrganizationRequest
    | Unset = UNSET
) -> Response[Organization]
```

Provides access to Organization details for the authenticated user.

Web-only endpoint - requires Auth0 authentication.
Organization management and billing operations require browser context.

**Arguments**:

  body (OrganizationRequest):
  body (OrganizationRequest):
  body (OrganizationRequest):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[Organization]

#### asyncio

```python
async def asyncio(
    *,
    client: AuthenticatedClient,
    body: OrganizationRequest
    | OrganizationRequest
    | OrganizationRequest
    | Unset = UNSET
) -> Organization | None
```

Provides access to Organization details for the authenticated user.

Web-only endpoint - requires Auth0 authentication.
Organization management and billing operations require browser context.

**Arguments**:

  body (OrganizationRequest):
  body (OrganizationRequest):
  body (OrganizationRequest):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Organization

