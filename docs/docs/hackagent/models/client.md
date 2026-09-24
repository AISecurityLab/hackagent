---
sidebar_label: client
title: hackagent.models.client
---

The :class:`~hackagent.core.contracts.LLM` implementation and `connect`.

## EnvelopeLLM Objects

```python
class EnvelopeLLM()
```

An :class:`LLM` whose calls go through a response envelope.

Subclasses implement :meth:`send` and :meth:`asend`, which take a request
dict and return the envelope; `complete` and `acomplete` convert it
into a :class:`Completion`. The techniques still call `send` (through
`attacks._lib.llm_router`) until they move to `complete`.

## ModelClient Objects

```python
class ModelClient(EnvelopeLLM)
```

One connected model or agent. Build it with :func:`connect`.

`with_params` returns a new client sharing the same adapter, with
call parameters that apply whenever a request does not set them. The
adapter itself is never mutated, so run-scoped parameters are safe
under parallel goals.

#### params

```python
@property
def params() -> Dict[str, Any]
```

The parameters set with :meth:`with_params`.

#### describe

```python
def describe() -> ModelSpec
```

The spec this client was connected with, plus its parameters.

#### connect

```python
def connect(spec: ModelSpec,
            *,
            instance_id: Optional[str] = None) -> ModelClient
```

Connect to the model `spec` describes. Does no network I/O.

**Arguments**:

- `spec` - The model to reach. ADK agents read `user_id` from
  `spec.extra`.
- `instance_id` - Identifies this client in logs and in the LiteLLM
  provider names the adapters register. Defaults to a random id.
  

**Raises**:

- `ValueError` - If the agent type is unsupported or the adapter rejects
  the spec.

