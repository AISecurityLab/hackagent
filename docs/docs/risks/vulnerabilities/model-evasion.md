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

**Objective**: `jailbreak`

### Recommended Datasets

**Primary**
- **advbench**: Adversarial benchmarks for evaluating evasion resistance

**Secondary**
- **xstest**: XSTest for adversarial prompt detection

### Attack Techniques

**Primary**
- **Static Template**: Template-based prompt injection
- **PAIR**: Iterative refinement for bypass discovery

**Secondary**
- **AdvPrefix**: Adversarial prefix optimisation

### Metrics

- asr
- judge_score

## Usage

### Instantiate the Vulnerability

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

### Run an Evaluation Campaign

```python
from hackagent import HackAgent
from hackagent.risks.model_evasion import MODEL_EVASION_PROFILE

agent = HackAgent(endpoint="http://localhost:8080/chat", name="my-agent")

# Profile techniques use display casing (e.g. "StaticTemplate");
# HackAgent.hack() expects the registered snake_case attack_type key.
ATTACK_TYPE_KEYS = {"StaticTemplate": "static_template", "PAIR": "pair"}

# Use profile recommendations
for attack in MODEL_EVASION_PROFILE.primary_attacks:
    for dataset in MODEL_EVASION_PROFILE.primary_datasets:
        attack_config = {
            "attack_type": ATTACK_TYPE_KEYS[attack.technique],
            "objective": MODEL_EVASION_PROFILE.objective,
            "dataset": {"preset": dataset.preset},
        }
        results = agent.hack(attack_config=attack_config)
        print(f"Results: {results}")
```
