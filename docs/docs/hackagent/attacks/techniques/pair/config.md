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

Pydantic defaults are the single source of truth (Phase 4). Attacker
``max_tokens`` is 500 to preserve the prior live PAIR runtime default
that ``DEFAULT_PAIR_CONFIG`` historically encoded via fallbacks / TUI.

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

#### default\_pair\_config

```python
def default_pair_config() -> Dict[str, Any]
```

Return a fresh PAIR defaults dict from :class:`PairConfig`.

