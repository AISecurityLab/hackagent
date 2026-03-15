---
sidebar_label: base
title: hackagent.attacks.objectives.base
---

Base objective class defining the interface for attack objectives.

Objectives define WHAT vulnerability we&#x27;re testing for, providing:
- Success/failure patterns for evaluation
- Evaluation criteria for judge models
- Objective-specific context for attack generation

Note: Objectives are metadata providers, not execution classes.
Actual attacks follow: AttackStrategy → BaseAttack → Pipeline stages

## ObjectiveConfig Objects

```python
class ObjectiveConfig()
```

Configuration and metadata for an attack objective.

This is a lightweight config class, NOT an abstract base for execution.
It provides objective-specific information that techniques can use.

Usage:
    # Define objective metadata
    prompt_injection = ObjectiveConfig(
        name=&quot;prompt_injection&quot;,
        success_patterns=[...],
        evaluation_criteria=&quot;...&quot;
    )

    # Use in attack configuration
    attack_config = &#123;
        &quot;objective&quot;: &quot;prompt_injection&quot;,
        &quot;technique&quot;: &quot;advprefix&quot;,  # or &quot;template&quot;
        &quot;goals&quot;: [...]
    &#125;

#### \_\_init\_\_

```python
def __init__(name: str,
             success_patterns: List[str],
             failure_patterns: List[str],
             evaluation_criteria: str,
             description: str = "")
```

Initialize objective configuration.

**Arguments**:

- `name` - Objective identifier (e.g., &quot;prompt_injection&quot;)
- `success_patterns` - Regex patterns indicating attack success
- `failure_patterns` - Regex patterns indicating attack failure
- `evaluation_criteria` - Description for judge models
- `description` - Human-readable description

#### to\_dict

```python
def to_dict() -> Dict
```

Convert to dictionary for serialization.

