---
sidebar_label: config
title: hackagent.attacks.techniques.baseline.config
---

Configuration for baseline attacks.

Baseline attacks use predefined prompt patterns to attempt jailbreaks,
combining templates with goals to generate attack prompts.

## TemplateAttackConfig Objects

```python
@dataclass
class TemplateAttackConfig()
```

Configuration for baseline attack pipeline.

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

