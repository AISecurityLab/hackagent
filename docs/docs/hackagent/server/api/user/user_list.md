---
sidebar_label: user_list
title: hackagent.server.api.user.user_list
---

#### sync\_detailed

```python
def sync_detailed(
        *,
        client: AuthenticatedClient,
        page: int | Unset = UNSET) -> Response[PaginatedUserProfileList]
```

Provides access to the UserProfile for the authenticated user.
Allows updating fields like the linked user&#x27;s first_name, last_name, email.

Web-only endpoint - requires Auth0 authentication.
User profile management requires OAuth context and is not for SDK use.

**Arguments**:

  page (int | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[PaginatedUserProfileList]

#### sync

```python
def sync(*,
         client: AuthenticatedClient,
         page: int | Unset = UNSET) -> PaginatedUserProfileList | None
```

Provides access to the UserProfile for the authenticated user.
Allows updating fields like the linked user&#x27;s first_name, last_name, email.

Web-only endpoint - requires Auth0 authentication.
User profile management requires OAuth context and is not for SDK use.

**Arguments**:

  page (int | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  PaginatedUserProfileList

#### asyncio\_detailed

```python
async def asyncio_detailed(
        *,
        client: AuthenticatedClient,
        page: int | Unset = UNSET) -> Response[PaginatedUserProfileList]
```

Provides access to the UserProfile for the authenticated user.
Allows updating fields like the linked user&#x27;s first_name, last_name, email.

Web-only endpoint - requires Auth0 authentication.
User profile management requires OAuth context and is not for SDK use.

**Arguments**:

  page (int | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[PaginatedUserProfileList]

#### asyncio

```python
async def asyncio(
        *,
        client: AuthenticatedClient,
        page: int | Unset = UNSET) -> PaginatedUserProfileList | None
```

Provides access to the UserProfile for the authenticated user.
Allows updating fields like the linked user&#x27;s first_name, last_name, email.

Web-only endpoint - requires Auth0 authentication.
User profile management requires OAuth context and is not for SDK use.

**Arguments**:

  page (int | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  PaginatedUserProfileList

