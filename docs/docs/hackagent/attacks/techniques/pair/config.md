---
sidebar_label: config
title: hackagent.attacks.techniques.pair.config
---

Configuration for PAIR attacks.

## PairConfig Objects

```python
class PairConfig(ConfigBase)
```

Complete typed configuration for the PAIR attack.

#### from\_dict

```python
@classmethod
def from_dict(cls, config_dict: Dict[str, Any]) -> "PairConfig"
```

Create a :class:`PairConfig` from a plain dictionary.

#### to\_dict

```python
def to_dict() -> Dict[str, Any]
```

Convert to dictionary suitable for :meth:`HackAgent.hack`.

