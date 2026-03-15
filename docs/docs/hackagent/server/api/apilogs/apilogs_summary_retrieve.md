---
sidebar_label: apilogs_summary_retrieve
title: hackagent.server.api.apilogs.apilogs_summary_retrieve
---

#### sync\_detailed

```python
def sync_detailed(*,
                  client: AuthenticatedClient,
                  by_key: bool | Unset = UNSET,
                  end_date: datetime.date,
                  start_date: datetime.date,
                  tz: str | Unset = UNSET) -> Response[APITokenLog]
```

Provides read-only access to APITokenLog entries for the user&#x27;s organization.

Web-only endpoint - requires Auth0 authentication.
Usage logs are intended for web dashboard monitoring.

**Arguments**:

  by_key (bool | Unset):
  end_date (datetime.date):
  start_date (datetime.date):
  tz (str | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[APITokenLog]

#### sync

```python
def sync(*,
         client: AuthenticatedClient,
         by_key: bool | Unset = UNSET,
         end_date: datetime.date,
         start_date: datetime.date,
         tz: str | Unset = UNSET) -> APITokenLog | None
```

Provides read-only access to APITokenLog entries for the user&#x27;s organization.

Web-only endpoint - requires Auth0 authentication.
Usage logs are intended for web dashboard monitoring.

**Arguments**:

  by_key (bool | Unset):
  end_date (datetime.date):
  start_date (datetime.date):
  tz (str | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  APITokenLog

#### asyncio\_detailed

```python
async def asyncio_detailed(*,
                           client: AuthenticatedClient,
                           by_key: bool | Unset = UNSET,
                           end_date: datetime.date,
                           start_date: datetime.date,
                           tz: str | Unset = UNSET) -> Response[APITokenLog]
```

Provides read-only access to APITokenLog entries for the user&#x27;s organization.

Web-only endpoint - requires Auth0 authentication.
Usage logs are intended for web dashboard monitoring.

**Arguments**:

  by_key (bool | Unset):
  end_date (datetime.date):
  start_date (datetime.date):
  tz (str | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[APITokenLog]

#### asyncio

```python
async def asyncio(*,
                  client: AuthenticatedClient,
                  by_key: bool | Unset = UNSET,
                  end_date: datetime.date,
                  start_date: datetime.date,
                  tz: str | Unset = UNSET) -> APITokenLog | None
```

Provides read-only access to APITokenLog entries for the user&#x27;s organization.

Web-only endpoint - requires Auth0 authentication.
Usage logs are intended for web dashboard monitoring.

**Arguments**:

  by_key (bool | Unset):
  end_date (datetime.date):
  start_date (datetime.date):
  tz (str | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  APITokenLog

