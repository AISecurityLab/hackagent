---
sidebar_label: adk
title: hackagent.models.completions.adk
---

Google ADK backend: proxy to an ADK server through a LiteLLM custom provider.

LiteLLM has no built-in provider for the ADK server protocol (`POST /run`
with sessions and events), so ADK is routed through LiteLLM by registering a
per-instance :class:`litellm.CustomLLM` handler under a unique provider name.
The HTTP transport against the deployed ADK server lives in the lazily-defined
`_ADKCustomLLM` class, while :class:`ADKModel` registers the handler and
dispatches requests through `litellm.completion`, returning a
:class:`ModelResponse` like every other backend.

## ADKConfigurationError Objects

```python
class ADKConfigurationError(Exception)
```

ADK backend configuration issues (missing name/endpoint/user_id).

## ADKInteractionError Objects

```python
class ADKInteractionError(Exception)
```

Errors interacting with the ADK agent server.

## ADKResponseParsingError Objects

```python
class ADKResponseParsingError(Exception)
```

Errors parsing the ADK server&#x27;s event-list response.

#### DEFAULT\_ADK\_USER\_ID

ADK sessions need a user id; used when the spec does not carry one. Matches
the default the legacy dispatch layer applied.

## ADKModel Objects

```python
class ADKModel(Model)
```

Native backend for a deployed Google ADK agent server.

Each instance registers its own :class:`litellm.CustomLLM` handler under a
unique provider name (`hackagent_adk_&lt;id&gt;`) so the call goes through
`litellm.completion` like every other LiteLLM provider — even though
LiteLLM has no built-in knowledge of the ADK `POST /run` + sessions +
events protocol.

Required config:
    - `name`: ADK app name (used as both the model string and the
      `app_name` in the request payload).
    - `endpoint`: ADK server base URL.
    - `user_id`: User ID for ADK sessions (read from `spec.extra`).

Optional config:
    - `timeout` (seconds, default 120).
    - `session_id`: sticky session ID; if unset a UUID is generated.
    - `fresh_session_per_request` (default True): if True, every request
      gets a brand-new session unless the caller supplies one.

