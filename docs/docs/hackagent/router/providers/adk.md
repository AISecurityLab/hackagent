---
sidebar_label: adk
title: hackagent.router.providers.adk
---

Google ADK (Agent Development Kit) provider built on top of LiteLLM.

LiteLLM has no built-in provider for the ADK server protocol (POST /run
with sessions and events), so issue `379` routes ADK through LiteLLM by
registering a per-instance :class:`litellm.CustomLLM` handler under a
unique provider name. The HTTP transport against the deployed ADK server
lives in the lazily-defined ``_ADKCustomLLM`` class, while
:class:`ADKAgent` registers the handler and dispatches requests via
``litellm.completion``. Since Phase E.2a, :class:`ADKAgent` extends
:class:`Agent` directly (not :class:`LiteLLMAgent`) so the chat-adapter
classes can be deleted in Phase E.2c without affecting ADK.

## AgentConfigurationError Objects

```python
class AgentConfigurationError(AdapterConfigurationError)
```

ADK adapter configuration issues.

## AgentInteractionError Objects

```python
class AgentInteractionError(AdapterInteractionError)
```

Errors interacting with the ADK agent server.

## ResponseParsingError Objects

```python
class ResponseParsingError(AdapterResponseParsingError)
```

Errors parsing the ADK server&#x27;s event-list response.

## ADKAgent Objects

```python
class ADKAgent(Agent)
```

Adapter for a deployed Google ADK agent server.

Each instance registers its own :class:`litellm.CustomLLM` handler
under a unique provider name (``hackagent_adk_&lt;id&gt;``) so the call
goes through ``litellm.completion`` like every other LiteLLM
provider — even though LiteLLM has no built-in knowledge of the
ADK ``POST /run`` + sessions + events protocol.

Required config:
    - ``name``: ADK app name (used as both the model string and the
      ``app_name`` in the request payload).
    - ``endpoint``: ADK server base URL.
    - ``user_id``: User ID for ADK sessions.

Optional config:
    - ``timeout`` (seconds, default 120).
    - ``session_id``: sticky session ID; if unset a UUID is generated.
    - ``fresh_session_per_request`` (default True): if True, every
      request gets a brand-new session unless the caller supplies one.

#### handle\_request

```python
def handle_request(request_data: Dict[str, Any]) -> Dict[str, Any]
```

Send a single ADK turn via ``litellm.completion``.

Implemented directly on :class:`ADKAgent` so the class no longer
depends on ``LiteLLMAgent`` (which Phase E.2c deletes). The
request flow is the same as before:

    request_data → litellm.completion(model=&quot;hackagent_adk_&lt;id&gt;/&lt;app&gt;&quot;,
                                      messages=…, session_id=…)
                  → _ADKCustomLLM.completion → ADK ``/run``

