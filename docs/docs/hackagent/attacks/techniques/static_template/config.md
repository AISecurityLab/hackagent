---
sidebar_label: config
title: hackagent.attacks.techniques.static_template.config
---

Configuration for static template attacks.

Static template attacks use predefined prompt patterns to attempt jailbreaks,
combining templates with goals to generate attack prompts.

## TemplateAttackConfig Objects

```python
class TemplateAttackConfig(ConfigBase)
```

Configuration for static template attack pipeline.

#### evaluator\_type

Deprecated compatibility field

#### from\_dict

```python
@classmethod
def from_dict(cls, config_dict: Dict[str, Any]) -> "TemplateAttackConfig"
```

Create config from dictionary.

#### to\_dict

```python
def to_dict() -> Dict[str, Any]
```

Convert to dictionary.

