---
sidebar_label: config
title: hackagent.attacks.techniques.autodan_turbo.config
---

Configuration for AutoDAN-Turbo attack technique.

AutoDAN-Turbo is a lifelong jailbreak attack that automatically discovers
and manages jailbreak strategies via a strategy library. It consists of
two phases:
1. Warm-up: Exploration-based attack to bootstrap strategy library
2. Lifelong: Strategy-guided attack with retrieval-augmented generation

Based on: https://arxiv.org/abs/2410.05295

## AutoDANTurboParams Objects

```python
class AutoDANTurboParams(BaseModel)
```

Typed AutoDAN-Turbo hyperparameters.

## AutoDANTurboConfig Objects

```python
class AutoDANTurboConfig(ConfigBase)
```

Complete typed configuration for AutoDAN-Turbo.

#### from\_dict

```python
@classmethod
def from_dict(cls, config_dict: Dict[str, Any]) -> "AutoDANTurboConfig"
```

Create an :class:`AutoDANTurboConfig` from a plain dictionary.

#### to\_dict

```python
def to_dict() -> Dict[str, Any]
```

Convert to dictionary suitable for :meth:`HackAgent.hack`.

