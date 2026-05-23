---
sidebar_label: agent
title: hackagent.router.agent
---

Agent base class + adapter exception types.

After issue `379` this module is the only piece of the old ``adapters/``
folder still in use. ``Agent`` is the abstract base that
:class:`hackagent.router.providers.adk.ADKAgent` inherits from to plug
non-chat-completion protocols into the router. Chat-completion
AgentTypes don&#x27;t go through ``Agent`` at all — they&#x27;re driven directly
from :class:`hackagent.router.router.AgentRouter` via
``_ChatRegistration``.

The ``AdapterConfigurationError`` / ``AdapterInteractionError`` /
``AdapterResponseParsingError`` names are kept (rather than renamed to
``AgentConfigurationError`` etc.) so existing ``except`` clauses in
attack code keep working.

## AdapterConfigurationError Objects

```python
class AdapterConfigurationError(Exception)
```

Base exception for adapter configuration issues.

## AdapterInteractionError Objects

```python
class AdapterInteractionError(Exception)
```

Base exception for errors during interaction with an agent API.

## AdapterResponseParsingError Objects

```python
class AdapterResponseParsingError(Exception)
```

Base exception for errors parsing an agent&#x27;s response.

## Agent Objects

```python
class Agent(ABC)
```

Abstract Base Class for all agent implementations.

It defines a common interface for the router to interact with various agents,
and provides shared functionality for logging, request validation, response
building, and configuration handling.

**Attributes**:

- `id` _str_ - Unique identifier for this agent instance.
- `config` _Dict[str, Any]_ - Configuration dictionary for this agent.
- `logger` _logging.Logger_ - Hierarchical logger instance.
- `model_name` _str_ - Name of the model (if applicable).
- `adapter_type` _str_ - Type identifier for the adapter (e.g., &quot;OpenAIAgent&quot;).
  
  Default Generation Parameters (optional, set by subclasses):
- `default_max_tokens` _int_ - Default maximum tokens to generate.
- `default_temperature` _float_ - Default sampling temperature.
- `default_top_p` _float_ - Default top-p sampling parameter.

#### \_\_init\_\_

```python
@abstractmethod
def __init__(id: str, config: Dict[str, Any])
```

Initializes the agent with common setup.

**Arguments**:

- `id` - A unique identifier for this specific agent instance or type.
- `config` - Configuration specific to this agent (e.g., API keys, model names).

#### adapter\_type

```python
@property
def adapter_type() -> str
```

Returns the adapter type name.

#### handle\_request

```python
@abstractmethod
def handle_request(request_data: Dict[str, Any]) -> Dict[str, Any]
```

Processes an incoming request and returns a standardized response.

The response should be suitable for storage via the API and should ideally
include enough information to reconstruct the interaction.

**Arguments**:

- `request_data` - The data for the agent to process. This might include
  the prompt, session information, user details, etc.
  Common keys:
  - &#x27;prompt&#x27;: Simple text prompt
  - &#x27;messages&#x27;: List of message dicts with &#x27;role&#x27; and &#x27;content&#x27;
  - &#x27;max_tokens&#x27;: Override default max tokens
  - &#x27;temperature&#x27;: Override default temperature
  - &#x27;top_p&#x27;: Override default top_p
  

**Returns**:

  A dictionary containing the standardized response with keys:
  - &#x27;raw_request&#x27;: The original request sent to the underlying agent.
  - &#x27;raw_response_body&#x27;: The raw response received from the underlying agent.
  - &#x27;raw_response_headers&#x27;: HTTP headers from the response if applicable.
  - &#x27;processed_response&#x27;: The key information extracted/processed.
  - &#x27;generated_text&#x27;: Alias for processed_response (for compatibility).
  - &#x27;status_code&#x27;: HTTP-like status code of the interaction.
  - &#x27;error_message&#x27;: Any error message encountered (None on success).
  - &#x27;agent_specific_data&#x27;: Adapter-specific metadata.
  - &#x27;agent_id&#x27;: The identifier of this agent.
  - &#x27;adapter_type&#x27;: The type of this adapter.

#### get\_identifier

```python
def get_identifier() -> str
```

Returns the unique identifier for this agent instance or type.

