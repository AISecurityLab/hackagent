---
sidebar_label: organization_me_retrieve
title: hackagent.server.api.organization.organization_me_retrieve
---

#### sync\_detailed

```python
def sync_detailed(*, client: AuthenticatedClient) -> Response[Organization]
```

Retrieve the organization for the currently authenticated user.

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[Organization]

#### sync

```python
def sync(*, client: AuthenticatedClient) -> Organization | None
```

Retrieve the organization for the currently authenticated user.

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Organization

#### asyncio\_detailed

```python
async def asyncio_detailed(
        *, client: AuthenticatedClient) -> Response[Organization]
```

Retrieve the organization for the currently authenticated user.

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[Organization]

#### asyncio

```python
async def asyncio(*, client: AuthenticatedClient) -> Organization | None
```

Retrieve the organization for the currently authenticated user.

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Organization

