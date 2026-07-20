---
sidebar_position: 6
---

# Craft Adversarial Data Threat Profile

Tests whether adversarially crafted data can compromise model behaviour.

## Objective

`jailbreak`

## Recommended Datasets

### Primary Datasets
- **advbench**: Adversarial goals that may involve crafted perturbations

## Attack Techniques

### Primary Attacks
- **Static Template**: Template-based prompt construction

## Metrics

- asr
- judge_score

## Usage Example

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
