---
sidebar_label: router
title: hackagent.router.router
---

## AgentRouter Objects

```python
class AgentRouter()
```

Manages the configuration and request routing for a single agent instance.

The `AgentRouter` is responsible for initializing an agent, which includes:
1.  Resolving organizational context via the storage backend.
2.  Ensuring the agent is registered in the storage backend.
3.  Instantiating the appropriate adapter (e.g., `ADKAgent`, `LiteLLMAgent`)
based on the `agent_type`.
4.  Storing this adapter for subsequent request routing.

**Attributes**:

- `backend` - The StorageBackend (RemoteBackend or LocalBackend).
- `organization_id` - The UUID of the organization associated with the backend.
- `user_id_str` - The string user ID associated with the backend context.
- `backend_agent` - The `AgentRecord` representing this agent in storage.
- `_agent_registry` - Dict mapping agent ID → instantiated adapter `ADKAgent`0 objects.

#### \_\_init\_\_

```python
def __init__(backend: StorageBackend,
             name: str,
             agent_type: AgentTypeEnum,
             endpoint: str,
             metadata=None,
             adapter_operational_config=None,
             overwrite_metadata: bool = True)
```

Initializes the AgentRouter and configures a single agent.

**Arguments**:

- `backend` - StorageBackend (RemoteBackend or LocalBackend).
- `name` - Name for the agent in storage.
- `agent_type` - The type of agent (e.g., AgentTypeEnum.LITELLM).
- `endpoint` - API endpoint URL for the agent service.
- `metadata` - Optional metadata to store with the agent record.
- `adapter_operational_config` - Runtime config for the adapter.
- `overwrite_metadata` - If True, update agent metadata when it differs.
  

**Raises**:

- `ValueError` - If the agent_type is unsupported or adapter init fails.
- `RuntimeError` - If backend communication fails.

#### get\_agent\_instance

```python
def get_agent_instance(registration_key: str) -> Optional[Agent]
```

Retrieves a registered agent adapter instance by its registration key.

The registration key is typically the backend ID of the agent.

**Arguments**:

- `registration_key` - The key (backend ID string) of the registered agent adapter.
  

**Returns**:

  The `Agent` adapter instance if found, otherwise `None`.

#### route\_request

```python
def route_request(registration_key: str,
                  request_data: Dict[str, Any],
                  raise_on_error: bool = False) -> Dict[str, Any]
```

Routes a request to the appropriate agent adapter and returns its response.

This method now follows a consistent error handling pattern: it returns standardized
error response dictionaries instead of raising exceptions by default. This ensures
that all code using the router can handle errors uniformly without try/except blocks.

**Arguments**:

- `registration_key` - The key (backend ID string) used to register the agent,
  which identifies the target adapter.
- `request_data` - A dictionary containing the data to be sent to the agent&#x27;s
  `handle_request` method.
- `raise_on_error` - If True, raises exceptions for errors (legacy behavior).
  If False (default), returns standardized error response dictionaries.
  

**Returns**:

  A dictionary containing either:
  - The successful response from the agent adapter, or
  - A standardized error response dictionary with error_message field
  

**Raises**:

- `ValueError` - Only if raise_on_error=True and no agent found for registration_key.
- `RuntimeError` - Only if raise_on_error=True and agent&#x27;s handle_request fails.
  

**Notes**:

  When raise_on_error=False (default), this method never raises exceptions,
  making it safer to use in pipelines where continuity is important.

