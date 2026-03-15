---
sidebar_label: user_me_update
title: hackagent.server.api.user.user_me_update
---

#### sync\_detailed

```python
def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: UserProfileRequest | UserProfileRequest | UserProfileRequest
    | Unset = UNSET
) -> Response[UserProfile]
```

Update the profile for the currently authenticated user.

**Arguments**:

  body (UserProfileRequest | Unset):
  body (UserProfileRequest | Unset):
  body (UserProfileRequest | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[UserProfile]

#### sync

```python
def sync(
    *,
    client: AuthenticatedClient,
    body: UserProfileRequest | UserProfileRequest | UserProfileRequest
    | Unset = UNSET
) -> UserProfile | None
```

Update the profile for the currently authenticated user.

**Arguments**:

  body (UserProfileRequest | Unset):
  body (UserProfileRequest | Unset):
  body (UserProfileRequest | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  UserProfile

#### asyncio\_detailed

```python
async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: UserProfileRequest | UserProfileRequest | UserProfileRequest
    | Unset = UNSET
) -> Response[UserProfile]
```

Update the profile for the currently authenticated user.

**Arguments**:

  body (UserProfileRequest | Unset):
  body (UserProfileRequest | Unset):
  body (UserProfileRequest | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[UserProfile]

#### asyncio

```python
async def asyncio(
    *,
    client: AuthenticatedClient,
    body: UserProfileRequest | UserProfileRequest | UserProfileRequest
    | Unset = UNSET
) -> UserProfile | None
```

Update the profile for the currently authenticated user.

**Arguments**:

  body (UserProfileRequest | Unset):
  body (UserProfileRequest | Unset):
  body (UserProfileRequest | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  UserProfile

