---
sidebar_label: dispatch
title: hackagent.models.dispatch
---

Build the adapter for a :class:`ModelSpec` and send requests through it.

Chat-completion agent types (``LITELLM``, ``OPENAI_SDK``, ``OLLAMA``,
``LANGCHAIN``) are driven through LiteLLM from a :class:`ProviderConfig`
and a ``_ChatRegistration``. The other supported types use an adapter class
whose ``handle_request`` does the call.

Sending never raises: every failure becomes an error envelope.

#### ADAPTER\_CLASSES

Agent types that need an adapter object rather than a chat registration.

#### DEFAULT\_ADK\_USER\_ID

ADK sessions need a user id; used when the spec does not carry one.

#### check\_supported

```python
def check_supported(agent_type: AgentType) -> None
```

Raise ``ValueError`` unless ``agent_type`` can be connected to.

#### resolve\_api\_key

```python
def resolve_api_key(spec: ModelSpec) -> Optional[str]
```

Return the spec&#x27;s API key: the literal one, else its env variable.

#### adapter\_config

```python
def adapter_config(spec: ModelSpec) -> Dict[str, Any]
```

Flatten ``spec`` into the config dict the adapters read.

#### build\_adapter

```python
def build_adapter(spec: ModelSpec, *, instance_id: str) -> Any
```

Instantiate the adapter for ``spec``. Does no network I/O.

**Raises**:

- `ValueError` - If the agent type is unsupported or the adapter rejects
  its configuration.

#### send

```python
def send(adapter: Any, agent_type: AgentType, request_data: Dict[str, Any], *,
         instance_id: str) -> Dict[str, Any]
```

Send one request through ``adapter`` and return its envelope.

#### asend

```python
async def asend(adapter: Any, agent_type: AgentType, request_data: Dict[str,
                                                                        Any],
                *, instance_id: str) -> Dict[str, Any]
```

Asynchronous :func:`send`; adapter-driven types run in a thread.

