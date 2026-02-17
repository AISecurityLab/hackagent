---
sidebar_position: 6
---

# Craft Adversarial Data

Tests whether adversarially crafted data — perturbations, poisoned examples, or augmentation abuse — can compromise model behaviour.

## Sub-types

- **Perturbation Attacks**: Small, imperceptible changes to inputs that alter model outputs.
- **Poisoned Examples**: Adversarially crafted examples designed to trigger specific model failures.
- **Data Augmentation Abuse**: Exploiting data augmentation pipelines to inject adversarial samples.

## Threat Profile

**Objective**: jailbreak

**Recommended Datasets**:
- **advbench** (PRIMARY): Adversarial goals that may involve crafted perturbations

**Attack Techniques**:
- Baseline (PRIMARY): Template-based prompt construction

**Metrics**: asr, judge_score

## Usage Example

```python
from hackagent.risks import CraftAdversarialData
from hackagent.risks.craft_adversarial_data.types import CraftAdversarialDataType

# Use all sub-types
vuln = CraftAdversarialData()

# Or specify particular sub-types
vuln = CraftAdversarialData(types=[
    CraftAdversarialDataType.PERTURBATION_ATTACKS.value,
    CraftAdversarialDataType.POISONED_EXAMPLES.value,
])
```
