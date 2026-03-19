---
sidebar_label: run_result_create
title: hackagent.server.api.run.run_result_create
---

#### sync\_detailed

```python
def sync_detailed(id: UUID, *, client: AuthenticatedClient,
                  body: ResultRequest) -> Response[Result]
```

Creates a new Result associated with this Run.
The run instance is fetched using the &#x27;id&#x27; (the lookup_field) from the URL.

**Arguments**:

  id (UUID):
- `body` _ResultRequest_ - Serializer for the Result model, often nested in RunSerializer.
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[Result]

#### sync

```python
def sync(id: UUID, *, client: AuthenticatedClient,
         body: ResultRequest) -> Result | None
```

Creates a new Result associated with this Run.
The run instance is fetched using the &#x27;id&#x27; (the lookup_field) from the URL.

**Arguments**:

  id (UUID):
- `body` _ResultRequest_ - Serializer for the Result model, often nested in RunSerializer.
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Result

#### asyncio\_detailed

```python
async def asyncio_detailed(id: UUID, *, client: AuthenticatedClient,
                           body: ResultRequest) -> Response[Result]
```

Creates a new Result associated with this Run.
The run instance is fetched using the &#x27;id&#x27; (the lookup_field) from the URL.

**Arguments**:

  id (UUID):
- `body` _ResultRequest_ - Serializer for the Result model, often nested in RunSerializer.
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[Result]

#### asyncio

```python
async def asyncio(id: UUID, *, client: AuthenticatedClient,
                  body: ResultRequest) -> Result | None
```

Creates a new Result associated with this Run.
The run instance is fetched using the &#x27;id&#x27; (the lookup_field) from the URL.

**Arguments**:

  id (UUID):
- `body` _ResultRequest_ - Serializer for the Result model, often nested in RunSerializer.
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Result

