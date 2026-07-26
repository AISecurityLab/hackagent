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

**Objective**: `jailbreak`

### Recommended Datasets

**Primary**
- **advbench**: Adversarial goals that may involve crafted perturbations

### Attack Techniques

**Primary**
- **Static Template**: Template-based prompt construction

### Metrics

- asr
- judge_score

## Usage

### Instantiate the Vulnerability

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

### Run an Evaluation Campaign

```python
from hackagent import HackAgent
from hackagent.risks.craft_adversarial_data import CRAFT_ADVERSARIAL_DATA_PROFILE

agent = HackAgent(endpoint="http://localhost:8080/chat", name="my-agent")

# Use profile recommendations
for attack in CRAFT_ADVERSARIAL_DATA_PROFILE.primary_attacks:
    for dataset in CRAFT_ADVERSARIAL_DATA_PROFILE.primary_datasets:
        attack_config = {
            "attack_type": attack.technique.lower(),
            "objective": CRAFT_ADVERSARIAL_DATA_PROFILE.objective,
            "dataset": {"preset": dataset.preset},
        }
        results = agent.hack(attack_config=attack_config)
        print(f"Results: {results}")
```
