---
sidebar_label: target_params
title: hackagent.models.target_params
---

Target generation parameters (moved out of attack configs).

Preferred runtime source remains `Target(..., target_config=...)` on the facade.
This typed model is the home for those knobs once technique configs stop
inheriting them from
the target model.

## TargetParams Objects

```python
class TargetParams(BaseModel)
```

Default generation parameters for the target (victim) model.

#### default\_target

```python
def default_target() -> Dict[str, Any]
```

A fresh dict of the target&#x27;s default generation parameters.

