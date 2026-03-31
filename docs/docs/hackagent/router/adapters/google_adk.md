---
sidebar_label: google_adk
title: hackagent.router.adapters.google_adk
---

## AgentConfigurationError Objects

```python
class AgentConfigurationError(AdapterConfigurationError)
```

Custom exception for agent configuration issues.

## AgentInteractionError Objects

```python
class AgentInteractionError(AdapterInteractionError)
```

Custom exception for errors during interaction with the agent API.

## ResponseParsingError Objects

```python
class ResponseParsingError(AdapterResponseParsingError)
```

Custom exception for errors parsing the agent&#x27;s response.

## ADKAgent Objects

```python
class ADKAgent(Agent)
```

Adapter for interacting with ADK (Agent Development Kit) based agents.

This class implements the common `Agent` interface. It translates requests
and responses between the router&#x27;s standard format and the specific format
required by ADK agents. It encapsulates all logic for ADK communication,
including session management (optional), request formatting, execution,
response parsing, and error handling.

**Attributes**:

- `name` _str_ - The name of the ADK application (used for router registration AND as ADK app identifier).
- `endpoint` _str_ - The base API endpoint for the ADK agent.
- `user_id` _str_ - The user identifier for ADK sessions.
- `timeout` _int_ - Timeout in seconds for requests to the ADK agent.
- `logger` _logging.Logger_ - Logger instance for this adapter.

#### \_\_init\_\_

```python
def __init__(id: str, config: Dict[str, Any])
```

Initializes the ADKAgent.

**Arguments**:

- `id` - The unique identifier for this ADK agent instance.
- `config` - Configuration dictionary for the ADK agent.
  Expected keys include:
  - &#x27;name&#x27;: Name of the ADK application (e.g., &#x27;multi_tool_agent&#x27;).
  - &#x27;endpoint&#x27;: Base URL of the ADK agent.
  - &#x27;user_id&#x27;: User ID for the ADK session.
  - &#x27;timeout&#x27; (optional): Request timeout in seconds
  (defaults to 120).
  

**Raises**:

- `AgentConfigurationError` - If any required configuration key (name, endpoint, user_id) is missing.

#### handle\_request

```python
def handle_request(request_data: Dict[str, Any]) -> Dict[str, Any]
```

Handles an incoming request by creating an ADK session (if not existing)
and then processing the request through the ADK agent.

**Arguments**:

- `request_data` - A dictionary containing the request data. Must include
  a &#x27;prompt&#x27; key with the text to send to the agent.
  Optional keys:
  - &#x27;session_id&#x27;: Override the adapter&#x27;s default session_id (advanced usage)
  - &#x27;initial_session_state&#x27;: Initial state dict for new sessions
  - &#x27;adk_session_id&#x27;: Deprecated, use &#x27;session_id&#x27; instead
  - &#x27;adk_user_id&#x27;: Deprecated, adapter manages user_id
  

**Returns**:

  A dictionary representing the agent&#x27;s response or an error.

