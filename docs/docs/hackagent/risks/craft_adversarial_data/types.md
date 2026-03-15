---
sidebar_label: types
title: hackagent.risks.craft_adversarial_data.types
---

Craft Adversarial Data sub-types.

## CraftAdversarialDataType Objects

```python
class CraftAdversarialDataType(Enum)
```

Sub-types for Craft Adversarial Data.

#### PERTURBATION\_ATTACKS

Small, imperceptible changes to inputs that alter model outputs.

#### POISONED\_EXAMPLES

Adversarially crafted examples designed to trigger specific model failures.

#### DATA\_AUGMENTATION\_ABUSE

Exploiting data augmentation pipelines to inject adversarial samples.

