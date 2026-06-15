---
sidebar_label: provider_config
title: hackagent.router.provider_config
---

``AgentType`` → ``ProviderConfig`` table.

The lookup table is the single source of truth for how each agent type
maps to a LiteLLM call: provider prefix, the ``thinking`` knob
translator, the allow-list of extra request keys that should pass
through, and an optional :class:`litellm.CustomLLM` factory for agent
types LiteLLM cannot speak natively (ADK, future MCP/A2A).

#### default\_thinking\_translator

```python
def default_thinking_translator(thinking: Any,
                                *,
                                model_name: str = "") -> Dict[str, Any]
```

Provider-agnostic translation that matches LiteLLM&#x27;s own conventions.

#### openai\_thinking\_translator

```python
def openai_thinking_translator(thinking: Any,
                               *,
                               model_name: str = "") -> Dict[str, Any]
```

Map ``thinking`` to ``reasoning_effort`` for OpenAI reasoning models.

#### ollama\_thinking\_translator

```python
def ollama_thinking_translator(thinking: Any,
                               *,
                               model_name: str = "") -> Dict[str, Any]
```

Map ``thinking`` to Ollama&#x27;s native ``think`` field.

## ProviderConfig Objects

```python
@dataclass(frozen=True)
class ProviderConfig()
```

Per-``AgentType`` knobs the router uses to drive ``litellm.completion``.

#### get\_provider\_config

```python
def get_provider_config(agent_type: AgentTypeEnum) -> Optional[ProviderConfig]
```

Return the ``ProviderConfig`` for ``agent_type``, or ``None``.

