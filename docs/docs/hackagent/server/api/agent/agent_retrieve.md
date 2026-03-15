---
sidebar_label: agent_retrieve
title: hackagent.server.api.agent.agent_retrieve
---

#### sync\_detailed

```python
def sync_detailed(id: UUID, *, client: AuthenticatedClient) -> Response[Agent]
```

Provides CRUD operations for Agent instances.

This ViewSet manages Agent records, ensuring that users can only interact
with agents based on their permissions and organizational context.
It filters agent listings for users and handles the logic for creating
agents, including associating them with the correct organization and owner.

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
Auth0 authentication is supported as fallback for web dashboard use.

Permissions are based on IsAuthenticated, with queryset filtering providing
row-level access control.

Class Attributes:
queryset (QuerySet): The default queryset for listing agents, initially all agents.
This is further filtered by `get_queryset()`.
serializer_class (AgentSerializer): The serializer used for validating and
deserializing input, and for serializing output.
authentication_classes (list): API Key (primary) + Auth0 (fallback) authentication.
permission_classes (list): List of permission classes to use.
parser_classes (list): List of parser classes for handling request data.
lookup_field (str): The model field used for looking up individual instances (UUID &#x27;id&#x27;).

**Arguments**:

  id (UUID):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[Agent]

#### sync

```python
def sync(id: UUID, *, client: AuthenticatedClient) -> Agent | None
```

Provides CRUD operations for Agent instances.

This ViewSet manages Agent records, ensuring that users can only interact
with agents based on their permissions and organizational context.
It filters agent listings for users and handles the logic for creating
agents, including associating them with the correct organization and owner.

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
Auth0 authentication is supported as fallback for web dashboard use.

Permissions are based on IsAuthenticated, with queryset filtering providing
row-level access control.

Class Attributes:
queryset (QuerySet): The default queryset for listing agents, initially all agents.
This is further filtered by `get_queryset()`.
serializer_class (AgentSerializer): The serializer used for validating and
deserializing input, and for serializing output.
authentication_classes (list): API Key (primary) + Auth0 (fallback) authentication.
permission_classes (list): List of permission classes to use.
parser_classes (list): List of parser classes for handling request data.
lookup_field (str): The model field used for looking up individual instances (UUID &#x27;id&#x27;).

**Arguments**:

  id (UUID):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Agent

#### asyncio\_detailed

```python
async def asyncio_detailed(id: UUID, *,
                           client: AuthenticatedClient) -> Response[Agent]
```

Provides CRUD operations for Agent instances.

This ViewSet manages Agent records, ensuring that users can only interact
with agents based on their permissions and organizational context.
It filters agent listings for users and handles the logic for creating
agents, including associating them with the correct organization and owner.

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
Auth0 authentication is supported as fallback for web dashboard use.

Permissions are based on IsAuthenticated, with queryset filtering providing
row-level access control.

Class Attributes:
queryset (QuerySet): The default queryset for listing agents, initially all agents.
This is further filtered by `get_queryset()`.
serializer_class (AgentSerializer): The serializer used for validating and
deserializing input, and for serializing output.
authentication_classes (list): API Key (primary) + Auth0 (fallback) authentication.
permission_classes (list): List of permission classes to use.
parser_classes (list): List of parser classes for handling request data.
lookup_field (str): The model field used for looking up individual instances (UUID &#x27;id&#x27;).

**Arguments**:

  id (UUID):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[Agent]

#### asyncio

```python
async def asyncio(id: UUID, *, client: AuthenticatedClient) -> Agent | None
```

Provides CRUD operations for Agent instances.

This ViewSet manages Agent records, ensuring that users can only interact
with agents based on their permissions and organizational context.
It filters agent listings for users and handles the logic for creating
agents, including associating them with the correct organization and owner.

SDK-primary endpoint - API Key authentication is recommended for programmatic access.
Auth0 authentication is supported as fallback for web dashboard use.

Permissions are based on IsAuthenticated, with queryset filtering providing
row-level access control.

Class Attributes:
queryset (QuerySet): The default queryset for listing agents, initially all agents.
This is further filtered by `get_queryset()`.
serializer_class (AgentSerializer): The serializer used for validating and
deserializing input, and for serializing output.
authentication_classes (list): API Key (primary) + Auth0 (fallback) authentication.
permission_classes (list): List of permission classes to use.
parser_classes (list): List of parser classes for handling request data.
lookup_field (str): The model field used for looking up individual instances (UUID &#x27;id&#x27;).

**Arguments**:

  id (UUID):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Agent

