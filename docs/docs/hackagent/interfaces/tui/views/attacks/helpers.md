---
sidebar_label: helpers
title: hackagent.interfaces.tui.views.attacks.helpers
---

Module-level helpers and constants for the Attacks tab.

#### model\_config\_from\_fields

```python
def model_config_from_fields(
        name: str,
        agent_type: Any,
        endpoint: str,
        *,
        options: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]
```

A campaign `ModelConfig` dict from a form&#x27;s name/type/endpoint fields.

Returns `None` when no name was entered (the model is unconfigured).
`options` carries backend-specific settings (a CLI agent&#x27;s `binary`,
ADK&#x27;s `user_id`, …); `extra` merges extra top-level keys such as a
judge&#x27;s `scoring`.

#### build\_guardrail\_config

```python
def build_guardrail_config(name: str, agent_type: Any,
                           endpoint: str) -> Optional[Dict[str, Any]]
```

A campaign guardrail `ModelConfig` from the form&#x27;s name/type/endpoint.

Returns `None` when no guardrail name was entered. The name is used
verbatim: model identifiers are case-sensitive. A guardrail is an
ordinary model in the spec (`GuardrailModelConfig`), so this is just a
named :func:`model_config_from_fields`.

