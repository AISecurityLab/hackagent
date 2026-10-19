---
sidebar_label: connect
title: hackagent.models.connect
---

Connect to the model a :class:`ModelSpec` describes, as a :class:`Model`.

This is the native replacement for the legacy `models.client.connect`: it
returns a :class:`Model` (`acomplete` → :class:`ModelResponse`) rather than an
envelope-based `ModelClient`. Native agent types (CLI agents, ADK, web) are
built straight from the spec so their `extra` options (binary, url, user_id…)
survive; LiteLLM chat providers go through the same `build_model` path as a
campaign, via a spec → :class:`ModelConfig` projection.

No network I/O happens here; an `api_key_env` that is not set fails when the
underlying model is built, so configuration errors surface before a run starts.

#### check\_supported

```python
def check_supported(agent_type: AgentType) -> None
```

Raise `ValueError` unless `agent_type` can be connected to.

#### connect

```python
def connect(spec: ModelSpec, *, instance_id: Optional[str] = None) -> Model
```

Build the :class:`Model` `spec` describes. Does no network I/O.

`instance_id` is accepted for call-site compatibility and ignored: a
native model names its own LiteLLM provider instance.

