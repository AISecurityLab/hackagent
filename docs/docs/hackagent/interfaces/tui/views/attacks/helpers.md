---
sidebar_label: helpers
title: hackagent.interfaces.tui.views.attacks.helpers
---

Module-level helpers and constants for the Attacks tab.

#### build\_guardrail\_config

```python
def build_guardrail_config(name: str, agent_type: Any,
                           endpoint: str) -> Optional[Dict[str, str]]
```

Build a guardrail config dict from the form&#x27;s name/type/endpoint fields.

Returns `None` when no guardrail name was entered. The name is used
verbatim: model identifiers are case-sensitive.

