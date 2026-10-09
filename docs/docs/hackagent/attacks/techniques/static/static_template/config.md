---
sidebar_label: config
title: hackagent.attacks.techniques.static.static_template.config
---

Configuration for the static-template attack.

#### BUILT\_IN\_PLACEHOLDERS

Placeholders the attack fills from the goal itself.

## StaticTemplateParams Objects

```python
class StaticTemplateParams(AttackParams)
```

Which templates to apply and the values for their extra placeholders.

#### selected\_templates

```python
def selected_templates() -> list[str]
```

Templates to apply, in stable category order.

