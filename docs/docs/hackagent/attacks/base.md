---
sidebar_label: base
title: hackagent.attacks.base
---

## BaseAttack Objects

```python
class BaseAttack(abc.ABC)
```

Abstract base class for black-box attacks against language models.

This class provides the foundational interface and structure that all
attack implementations must follow. It handles common initialization
patterns and enforces a consistent API across different attack types.

**Attributes**:

- `config` - A dictionary containing configuration settings for the attack.

#### \_\_init\_\_

```python
def __init__(config: Dict[str, Any])
```

Initializes the attack with configuration parameters.

**Arguments**:

- `config` - A dictionary containing configuration settings for the attack.
  Must include all required parameters for the specific attack type.
  

**Raises**:

- `TypeError` - If config is not a dictionary.
- `ValueError` - If required configuration parameters are missing or invalid.

#### run

```python
@abc.abstractmethod
def run(**kwargs: Any) -> Any
```

Executes the attack logic.

This abstract method must be implemented by all attack subclasses
to define their specific attack methodology and execution flow.

**Arguments**:

- `**kwargs` - Attack-specific arguments that vary by implementation.
  Common examples include:
  - input_prompts: List of prompts to test
  - goals: List of target goals for the attack
  - dataset: Input dataset for evaluation
  - target_model: The model to attack
  

**Returns**:

  Attack-specific results. The format varies by implementation but
  typically includes:
  - adversarial_examples: Generated adversarial inputs
  - success_metrics: Attack success rates and statistics
  - detailed_results: Comprehensive result data (e.g., pandas DataFrame)
  - attack_report: Summary of attack performance
  

**Raises**:

- `NotImplementedError` - If the method is not implemented by a subclass.
- `RuntimeError` - If the attack execution fails due to configuration
  or runtime errors.

