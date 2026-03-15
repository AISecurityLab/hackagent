---
sidebar_label: key_context_retrieve
title: hackagent.server.api.key.key_context_retrieve
---

#### sync\_detailed

```python
def sync_detailed(
        *, client: AuthenticatedClient
) -> Response[KeyContextRetrieveResponse200]
```

Caller identity context

Returns the caller&#x27;s user ID, username, and organization details. Accessible with both API Key and
Auth0 bearer tokens. The SDK uses this endpoint to bootstrap organization context without needing to
page through the agent list.

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[KeyContextRetrieveResponse200]

#### sync

```python
def sync(*,
         client: AuthenticatedClient) -> KeyContextRetrieveResponse200 | None
```

Caller identity context

Returns the caller&#x27;s user ID, username, and organization details. Accessible with both API Key and
Auth0 bearer tokens. The SDK uses this endpoint to bootstrap organization context without needing to
page through the agent list.

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  KeyContextRetrieveResponse200

#### asyncio\_detailed

```python
async def asyncio_detailed(
        *, client: AuthenticatedClient
) -> Response[KeyContextRetrieveResponse200]
```

Caller identity context

Returns the caller&#x27;s user ID, username, and organization details. Accessible with both API Key and
Auth0 bearer tokens. The SDK uses this endpoint to bootstrap organization context without needing to
page through the agent list.

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[KeyContextRetrieveResponse200]

#### asyncio

```python
async def asyncio(
        *,
        client: AuthenticatedClient) -> KeyContextRetrieveResponse200 | None
```

Caller identity context

Returns the caller&#x27;s user ID, username, and organization details. Accessible with both API Key and
Auth0 bearer tokens. The SDK uses this endpoint to bootstrap organization context without needing to
page through the agent list.

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  KeyContextRetrieveResponse200

