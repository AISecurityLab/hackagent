---
sidebar_position: 5
---

# Model Evasion

Tests whether adversarial examples, feature manipulation, or boundary exploitation can evade the model's safety mechanisms.

## Sub-types

- **Adversarial Examples**: Crafted inputs that cause the model to misclassify or produce wrong outputs.
- **Feature Space Manipulation**: Manipulating input features to evade detection or safety mechanisms.
- **Model Boundary Exploitation**: Exploiting decision boundaries to find blind spots in model behaviour.

## Threat Profile

**Objective**: jailbreak

**Recommended Datasets**:
- **advbench** (PRIMARY): Adversarial benchmarks for evaluating evasion resistance
- **xstest** (SECONDARY): XSTest for adversarial prompt detection

**Attack Techniques**:
- Baseline (PRIMARY): Template-based prompt injection
- PAIR (PRIMARY): Iterative refinement for bypass discovery
- AdvPrefix (SECONDARY): Adversarial prefix optimisation

**Metrics**: asr, judge_score

## Usage Example

```python
from hackagent.risks import ModelEvasion
from hackagent.risks.model_evasion.types import ModelEvasionType

# Use all sub-types
vuln = ModelEvasion()

# Or specify particular sub-types
vuln = ModelEvasion(types=[
    ModelEvasionType.ADVERSARIAL_EXAMPLES.value,
    ModelEvasionType.MODEL_BOUNDARY_EXPLOITATION.value,
])
```
