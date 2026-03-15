---
sidebar_label: attack_list
title: hackagent.server.api.attack.attack_list
---

#### sync\_detailed

```python
def sync_detailed(*,
                  client: AuthenticatedClient,
                  page: int | Unset = UNSET) -> Response[PaginatedAttackList]
```

Manages Attack configurations through standard CRUD operations.

This ViewSet allows clients to:
- Create new Attack configurations.
- List existing Attack configurations (with filtering based on user/org).
- Retrieve details of a specific Attack configuration.
- Update an existing Attack configuration.
- Delete an Attack configuration.

The actual execution of an attack based on these configurations, and the
management of run statuses or results, are handled by other parts of the API
(e.g., potentially a RunViewSet or similar).

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
Auth0 authentication is supported as fallback for web dashboard use.

**Attributes**:

- `queryset` - The base queryset, retrieving all Attack objects with related
  entities (agent, owner, organization) pre-fetched.
- `serializer_class` - The serializer (`AttackSerializer`) used for data
  conversion for Attack configurations.
- `authentication_classes` - API Key (primary) + Auth0 (fallback) authentication.
- `permission_classes` - List of permission enforcement classes.
- `parser_classes` - List of parsers for request data (JSONParser).
- `lookup_field` - The model field used for looking up individual instances (&#x27;id&#x27;).
  

**Arguments**:

  page (int | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[PaginatedAttackList]

#### sync

```python
def sync(*,
         client: AuthenticatedClient,
         page: int | Unset = UNSET) -> PaginatedAttackList | None
```

Manages Attack configurations through standard CRUD operations.

This ViewSet allows clients to:
- Create new Attack configurations.
- List existing Attack configurations (with filtering based on user/org).
- Retrieve details of a specific Attack configuration.
- Update an existing Attack configuration.
- Delete an Attack configuration.

The actual execution of an attack based on these configurations, and the
management of run statuses or results, are handled by other parts of the API
(e.g., potentially a RunViewSet or similar).

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
Auth0 authentication is supported as fallback for web dashboard use.

**Attributes**:

- `queryset` - The base queryset, retrieving all Attack objects with related
  entities (agent, owner, organization) pre-fetched.
- `serializer_class` - The serializer (`AttackSerializer`) used for data
  conversion for Attack configurations.
- `authentication_classes` - API Key (primary) + Auth0 (fallback) authentication.
- `permission_classes` - List of permission enforcement classes.
- `parser_classes` - List of parsers for request data (JSONParser).
- `lookup_field` - The model field used for looking up individual instances (&#x27;id&#x27;).
  

**Arguments**:

  page (int | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  PaginatedAttackList

#### asyncio\_detailed

```python
async def asyncio_detailed(
        *,
        client: AuthenticatedClient,
        page: int | Unset = UNSET) -> Response[PaginatedAttackList]
```

Manages Attack configurations through standard CRUD operations.

This ViewSet allows clients to:
- Create new Attack configurations.
- List existing Attack configurations (with filtering based on user/org).
- Retrieve details of a specific Attack configuration.
- Update an existing Attack configuration.
- Delete an Attack configuration.

The actual execution of an attack based on these configurations, and the
management of run statuses or results, are handled by other parts of the API
(e.g., potentially a RunViewSet or similar).

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
Auth0 authentication is supported as fallback for web dashboard use.

**Attributes**:

- `queryset` - The base queryset, retrieving all Attack objects with related
  entities (agent, owner, organization) pre-fetched.
- `serializer_class` - The serializer (`AttackSerializer`) used for data
  conversion for Attack configurations.
- `authentication_classes` - API Key (primary) + Auth0 (fallback) authentication.
- `permission_classes` - List of permission enforcement classes.
- `parser_classes` - List of parsers for request data (JSONParser).
- `lookup_field` - The model field used for looking up individual instances (&#x27;id&#x27;).
  

**Arguments**:

  page (int | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[PaginatedAttackList]

#### asyncio

```python
async def asyncio(*,
                  client: AuthenticatedClient,
                  page: int | Unset = UNSET) -> PaginatedAttackList | None
```

Manages Attack configurations through standard CRUD operations.

This ViewSet allows clients to:
- Create new Attack configurations.
- List existing Attack configurations (with filtering based on user/org).
- Retrieve details of a specific Attack configuration.
- Update an existing Attack configuration.
- Delete an Attack configuration.

The actual execution of an attack based on these configurations, and the
management of run statuses or results, are handled by other parts of the API
(e.g., potentially a RunViewSet or similar).

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
Auth0 authentication is supported as fallback for web dashboard use.

**Attributes**:

- `queryset` - The base queryset, retrieving all Attack objects with related
  entities (agent, owner, organization) pre-fetched.
- `serializer_class` - The serializer (`AttackSerializer`) used for data
  conversion for Attack configurations.
- `authentication_classes` - API Key (primary) + Auth0 (fallback) authentication.
- `permission_classes` - List of permission enforcement classes.
- `parser_classes` - List of parsers for request data (JSONParser).
- `lookup_field` - The model field used for looking up individual instances (&#x27;id&#x27;).
  

**Arguments**:

  page (int | Unset):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  PaginatedAttackList

