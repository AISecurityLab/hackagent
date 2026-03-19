---
sidebar_label: agent_update
title: hackagent.server.api.agent.agent_update
---

#### sync\_detailed

```python
def sync_detailed(id: UUID, *, client: AuthenticatedClient,
                  body: AgentRequest) -> Response[Agent]
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
- `body` _AgentRequest_ - Serializes Agent model instances to JSON and validates data for
  creating
  or updating Agent instances.
  
  This serializer provides a comprehensive representation of an Agent,
  including its type, endpoint, and nested details for related &#x27;organization&#x27;
  and &#x27;owner&#x27; for read operations, while allowing &#x27;organization&#x27; and &#x27;owner&#x27; IDs
  for write operations.
  

**Attributes**:

- `organization_detail` _OrganizationMinimalSerializer_ - Read-only nested
  serializer for the agent&#x27;s organization. Displays minimal details.
- `owner_detail` _UserProfileMinimalSerializer_ - Read-only nested serializer
  for the agent&#x27;s owner&#x27;s user profile. Displays minimal details.
  Can be null if the agent has no owner or the owner has no profile.
- `agent_type` _CharField_ - The type of the agent as a string
  (e.g., LITELLM, OPENAI_SDK, GOOGLE_ADK).
  
  Meta:
- `model` _Agent_ - The model class that this serializer works with.
- `fields` _tuple_ - The fields to include in the serialized output.
  Includes standard Agent fields like &#x27;endpoint&#x27;, &#x27;type&#x27;,
  and the read-only nested details.
- `read_only_fields` _tuple_ - Fields that are read-only and cannot be
  set during create/update operations through this serializer.
  This includes &#x27;id&#x27;, &#x27;created_at&#x27;, &#x27;updated_at&#x27;, and the
  nested detail fields.
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[Agent]

#### sync

```python
def sync(id: UUID, *, client: AuthenticatedClient,
         body: AgentRequest) -> Agent | None
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
- `body` _AgentRequest_ - Serializes Agent model instances to JSON and validates data for
  creating
  or updating Agent instances.
  
  This serializer provides a comprehensive representation of an Agent,
  including its type, endpoint, and nested details for related &#x27;organization&#x27;
  and &#x27;owner&#x27; for read operations, while allowing &#x27;organization&#x27; and &#x27;owner&#x27; IDs
  for write operations.
  

**Attributes**:

- `organization_detail` _OrganizationMinimalSerializer_ - Read-only nested
  serializer for the agent&#x27;s organization. Displays minimal details.
- `owner_detail` _UserProfileMinimalSerializer_ - Read-only nested serializer
  for the agent&#x27;s owner&#x27;s user profile. Displays minimal details.
  Can be null if the agent has no owner or the owner has no profile.
- `agent_type` _CharField_ - The type of the agent as a string
  (e.g., LITELLM, OPENAI_SDK, GOOGLE_ADK).
  
  Meta:
- `model` _Agent_ - The model class that this serializer works with.
- `fields` _tuple_ - The fields to include in the serialized output.
  Includes standard Agent fields like &#x27;endpoint&#x27;, &#x27;type&#x27;,
  and the read-only nested details.
- `read_only_fields` _tuple_ - Fields that are read-only and cannot be
  set during create/update operations through this serializer.
  This includes &#x27;id&#x27;, &#x27;created_at&#x27;, &#x27;updated_at&#x27;, and the
  nested detail fields.
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Agent

#### asyncio\_detailed

```python
async def asyncio_detailed(id: UUID, *, client: AuthenticatedClient,
                           body: AgentRequest) -> Response[Agent]
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
- `body` _AgentRequest_ - Serializes Agent model instances to JSON and validates data for
  creating
  or updating Agent instances.
  
  This serializer provides a comprehensive representation of an Agent,
  including its type, endpoint, and nested details for related &#x27;organization&#x27;
  and &#x27;owner&#x27; for read operations, while allowing &#x27;organization&#x27; and &#x27;owner&#x27; IDs
  for write operations.
  

**Attributes**:

- `organization_detail` _OrganizationMinimalSerializer_ - Read-only nested
  serializer for the agent&#x27;s organization. Displays minimal details.
- `owner_detail` _UserProfileMinimalSerializer_ - Read-only nested serializer
  for the agent&#x27;s owner&#x27;s user profile. Displays minimal details.
  Can be null if the agent has no owner or the owner has no profile.
- `agent_type` _CharField_ - The type of the agent as a string
  (e.g., LITELLM, OPENAI_SDK, GOOGLE_ADK).
  
  Meta:
- `model` _Agent_ - The model class that this serializer works with.
- `fields` _tuple_ - The fields to include in the serialized output.
  Includes standard Agent fields like &#x27;endpoint&#x27;, &#x27;type&#x27;,
  and the read-only nested details.
- `read_only_fields` _tuple_ - Fields that are read-only and cannot be
  set during create/update operations through this serializer.
  This includes &#x27;id&#x27;, &#x27;created_at&#x27;, &#x27;updated_at&#x27;, and the
  nested detail fields.
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[Agent]

#### asyncio

```python
async def asyncio(id: UUID, *, client: AuthenticatedClient,
                  body: AgentRequest) -> Agent | None
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
- `body` _AgentRequest_ - Serializes Agent model instances to JSON and validates data for
  creating
  or updating Agent instances.
  
  This serializer provides a comprehensive representation of an Agent,
  including its type, endpoint, and nested details for related &#x27;organization&#x27;
  and &#x27;owner&#x27; for read operations, while allowing &#x27;organization&#x27; and &#x27;owner&#x27; IDs
  for write operations.
  

**Attributes**:

- `organization_detail` _OrganizationMinimalSerializer_ - Read-only nested
  serializer for the agent&#x27;s organization. Displays minimal details.
- `owner_detail` _UserProfileMinimalSerializer_ - Read-only nested serializer
  for the agent&#x27;s owner&#x27;s user profile. Displays minimal details.
  Can be null if the agent has no owner or the owner has no profile.
- `agent_type` _CharField_ - The type of the agent as a string
  (e.g., LITELLM, OPENAI_SDK, GOOGLE_ADK).
  
  Meta:
- `model` _Agent_ - The model class that this serializer works with.
- `fields` _tuple_ - The fields to include in the serialized output.
  Includes standard Agent fields like &#x27;endpoint&#x27;, &#x27;type&#x27;,
  and the read-only nested details.
- `read_only_fields` _tuple_ - Fields that are read-only and cannot be
  set during create/update operations through this serializer.
  This includes &#x27;id&#x27;, &#x27;created_at&#x27;, &#x27;updated_at&#x27;, and the
  nested detail fields.
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Agent

