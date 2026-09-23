---
sidebar_label: llm_router
title: hackagent.attacks._lib.llm_router
---

The ``route_request`` surface the techniques call, over an LLM.

The techniques still call ``router.route_request(registration_key=...,
request_data=...)`` and read ``backend_agent`` and ``_agent_registry``.
:class:`LLMRouter` presents an :class:`~hackagent.models.EnvelopeLLM`
that way, with no storage behind it. It goes away once the techniques
call ``LLM.complete`` (Phase 5 of `640`).

## ModelInfo Objects

```python
@dataclass(frozen=True)
class ModelInfo()
```

What the techniques read off ``router.backend_agent``.

## LLMRouter Objects

```python
class LLMRouter()
```

Routes ``route_request`` calls to one LLM.

**Arguments**:

- `llm` - The model to call.
- `agent` - Identity to expose as ``backend_agent``; the target passes
  its Agent record. Defaults to one derived from the LLM&#x27;s spec.

#### with\_params

```python
def with_params(**params: Any) -> "LLMRouter"
```

A router over ``llm.with_params(...)`` with the same identity.

#### route\_request

```python
def route_request(registration_key: str,
                  request_data: Dict[str, Any]) -> Dict[str, Any]
```

Send ``request_data`` and return the response envelope.

#### route\_request\_async

```python
async def route_request_async(registration_key: str,
                              request_data: Dict[str, Any]) -> Dict[str, Any]
```

Asynchronous :meth:`route_request`.

#### connect\_role

```python
def connect_role(config: Dict[str, Any],
                 *,
                 name: Optional[str] = None,
                 models: Any = None) -> Tuple[LLMRouter, str]
```

Connect to the role model ``config`` describes.

When *models* (an ``LLMFactory`` from ``ctx.models``) is provided, the
role is built through ``models.for_role`` instead of a bare ``connect``.

Returns the router and its registration key. The model uses only the
credentials its config names.

**Raises**:

- `ValueError` - If the config is invalid or the adapter rejects it.

