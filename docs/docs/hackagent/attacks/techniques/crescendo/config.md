---
sidebar_label: config
title: hackagent.attacks.techniques.crescendo.config
---

Configuration for the Crescendo attack.

## CrescendoConfig Objects

```python
class CrescendoConfig(ConfigBase)
```

Complete typed configuration for the Crescendo attack.

#### from\_dict

```python
@classmethod
def from_dict(cls, config_dict: Dict[str, Any]) -> "CrescendoConfig"
```

Create a :class:`CrescendoConfig` from a plain dictionary.

#### to\_dict

```python
def to_dict() -> Dict[str, Any]
```

Convert to dictionary suitable for :meth:`HackAgent.hack`.

