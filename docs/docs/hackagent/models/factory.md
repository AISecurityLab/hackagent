---
sidebar_label: factory
title: hackagent.models.factory
---

Build role-model LLMs, with credentials from :class:`Settings`.

:class:`ModelFactory` implements the ``LLMFactory`` protocol. A role model
uses the key its spec names. The only credential the factory adds is the
HackAgent API key, and only for a spec whose endpoint is the hosted LLM
gateway; it is never sent to any other provider.

:func:`spec_from_config` reads the role-model dicts attack configs still
use (``identifier``, ``endpoint``, ``agent_type``, ``api_key`` given as a
literal or an environment variable name, ...).

#### PASSTHROUGH\_REQUEST\_KEYS

Provider request parameters a role config may set.

#### passthrough\_params

```python
def passthrough_params(config: Mapping[str, Any]) -> Dict[str, Any]
```

Return the provider request parameters set in ``config``.

#### spec\_from\_config

```python
def spec_from_config(
        config: Mapping[str, Any],
        *,
        spec_type: Type[SpecT] = ModelSpec,
        default_agent_type: AgentType = AgentType.OPENAI_SDK) -> SpecT
```

Build a spec from a role-model config dict.

A missing or invalid ``agent_type`` becomes ``default_agent_type``.
``model`` overrides ``identifier`` as the model name; ``request_timeout``
is accepted for ``timeout``; keys under ``agent_metadata`` fill any the
config leaves unset. ``thinking`` is kept only for Ollama, which is the
only role-model type that has ever honoured it. Fields of ``spec_type``
beyond :class:`ModelSpec` (e.g. ``system_prompt``) are read too.

**Raises**:

- `ValueError` - If the config has no ``identifier``.

## ModelFactory Objects

```python
class ModelFactory()
```

Builds the LLM for a role model. Implements ``LLMFactory``.

#### is\_gateway

```python
def is_gateway(endpoint: Optional[str]) -> bool
```

Whether ``endpoint`` is the hosted LLM gateway of a remote run.

#### with\_credentials

```python
def with_credentials(spec: SpecT) -> SpecT
```

Add the gateway key to a gateway spec that names no key.

