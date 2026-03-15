---
sidebar_label: base
title: hackagent.risks.base
---

Base vulnerability class for all hackagent risk assessments.

Architecture (mirrors the attack layer):
    HackAgent.hack() → AttackOrchestrator → BaseAttack (technique)
                                              ↕
                     BaseVulnerability ← vulnerability.assess()

Each concrete vulnerability:
  1. Defines an Enum of sub-types in its `types.py`
  2. Provides prompt templates in its `templates.py`
  3. Extends this class in its main module (e.g. `bias.py`)

## BaseVulnerability Objects

```python
class BaseVulnerability(abc.ABC)
```

Abstract base class for all vulnerabilities.

Each vulnerability carries an `Enum` of sub-types that can be individually selected.

Subclasses must set the class-level attributes:
    - `name`             – human-readable name
    - `description`      – one-liner for reports
    - `ALLOWED_TYPES`    – list of valid sub-type *values* (strings)
    - `_type_enum`       – the Enum class used for validation

Parameters
----------
types : list[Enum]
    Sub-types to evaluate (defaults to all allowed types).

#### get\_types

```python
def get_types() -> List[Enum]
```

Return the list of selected sub-type enums.

#### get\_values

```python
def get_values() -> List[str]
```

Return selected sub-type values as plain strings.

#### assess

```python
def assess(model_callback: Any = None,
           purpose: Optional[str] = None) -> Dict[str, Any]
```

Evaluate the target model for this vulnerability.

Returns a dict mapping each sub-type value to its test-case results.

#### a\_assess

```python
async def a_assess(model_callback: Any = None,
                   purpose: Optional[str] = None) -> Dict[str, Any]
```

Async variant of :pymeth:`assess`.

#### simulate\_attacks

```python
def simulate_attacks(purpose: Optional[str] = None) -> List[str]
```

Generate baseline attack prompts for each selected sub-type.

Returns a flat list of attack strings.

#### a\_simulate\_attacks

```python
async def a_simulate_attacks(purpose: Optional[str] = None) -> List[str]
```

Async variant of :pymeth:`simulate_attacks`.

