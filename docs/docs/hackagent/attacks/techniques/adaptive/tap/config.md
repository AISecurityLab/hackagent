---
sidebar_label: config
title: hackagent.attacks.techniques.adaptive.tap.config
---

Configuration for TAP (Tree of Attacks with Pruning).

This config mirrors HackAgent&#x27;s standard structure (e.g., FlipAttack/PAIR)
while exposing TAP-specific hyperparameters: depth, width, and branching_factor.

## TapParams Objects

```python
class TapParams(BaseModel)
```

TAP-specific parameters.

## TapConfig Objects

```python
class TapConfig(ConfigBase)
```

Complete TAP configuration for use with HackAgent.hack().

#### roles\_from\_mapping

```python
@classmethod
def roles_from_mapping(cls, data: Mapping[str, Any]) -> List[Dict[str, Any]]
```

TAP roles with on-topic judge falling back to the first judge.

#### from\_dict

```python
@classmethod
def from_dict(cls, config_dict: Dict[str, Any]) -> "TapConfig"
```

Create config from dictionary.

#### to\_dict

```python
def to_dict() -> Dict[str, Any]
```

Convert to dictionary.

