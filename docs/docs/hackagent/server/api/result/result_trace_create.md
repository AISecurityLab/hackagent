---
sidebar_label: result_trace_create
title: hackagent.server.api.result.result_trace_create
---

#### sync\_detailed

```python
def sync_detailed(id: UUID, *, client: AuthenticatedClient,
                  body: TraceRequest) -> Response[Trace]
```

Creates a new Trace associated with this Result.
The result instance is fetched using the &#x27;id&#x27; (the lookup_field) from the URL.

**Arguments**:

  id (UUID):
- `body` _TraceRequest_ - Serializer for the Trace model.
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[Trace]

#### sync

```python
def sync(id: UUID, *, client: AuthenticatedClient,
         body: TraceRequest) -> Trace | None
```

Creates a new Trace associated with this Result.
The result instance is fetched using the &#x27;id&#x27; (the lookup_field) from the URL.

**Arguments**:

  id (UUID):
- `body` _TraceRequest_ - Serializer for the Trace model.
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Trace

#### asyncio\_detailed

```python
async def asyncio_detailed(id: UUID, *, client: AuthenticatedClient,
                           body: TraceRequest) -> Response[Trace]
```

Creates a new Trace associated with this Result.
The result instance is fetched using the &#x27;id&#x27; (the lookup_field) from the URL.

**Arguments**:

  id (UUID):
- `body` _TraceRequest_ - Serializer for the Trace model.
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[Trace]

#### asyncio

```python
async def asyncio(id: UUID, *, client: AuthenticatedClient,
                  body: TraceRequest) -> Trace | None
```

Creates a new Trace associated with this Result.
The result instance is fetched using the &#x27;id&#x27; (the lookup_field) from the URL.

**Arguments**:

  id (UUID):
- `body` _TraceRequest_ - Serializer for the Trace model.
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Trace

