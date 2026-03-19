---
sidebar_label: user_retrieve
title: hackagent.server.api.user.user_retrieve
---

#### sync\_detailed

```python
def sync_detailed(id: UUID, *,
                  client: AuthenticatedClient) -> Response[UserProfile]
```

Provides access to the UserProfile for the authenticated user.
Allows updating fields like the linked user&#x27;s first_name, last_name, email.

Web-only endpoint - requires Auth0 authentication.
User profile management requires OAuth context and is not for SDK use.

**Arguments**:

  id (UUID):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[UserProfile]

#### sync

```python
def sync(id: UUID, *, client: AuthenticatedClient) -> UserProfile | None
```

Provides access to the UserProfile for the authenticated user.
Allows updating fields like the linked user&#x27;s first_name, last_name, email.

Web-only endpoint - requires Auth0 authentication.
User profile management requires OAuth context and is not for SDK use.

**Arguments**:

  id (UUID):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  UserProfile

#### asyncio\_detailed

```python
async def asyncio_detailed(
        id: UUID, *, client: AuthenticatedClient) -> Response[UserProfile]
```

Provides access to the UserProfile for the authenticated user.
Allows updating fields like the linked user&#x27;s first_name, last_name, email.

Web-only endpoint - requires Auth0 authentication.
User profile management requires OAuth context and is not for SDK use.

**Arguments**:

  id (UUID):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[UserProfile]

#### asyncio

```python
async def asyncio(id: UUID, *,
                  client: AuthenticatedClient) -> UserProfile | None
```

Provides access to the UserProfile for the authenticated user.
Allows updating fields like the linked user&#x27;s first_name, last_name, email.

Web-only endpoint - requires Auth0 authentication.
User profile management requires OAuth context and is not for SDK use.

**Arguments**:

  id (UUID):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  UserProfile

