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
- **Baseline**: Template-based prompt construction

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
        result = agent.attack(
            attack_type=attack.technique.lower(),
            dataset=dataset.preset,
            objective=CRAFT_ADVERSARIAL_DATA_PROFILE.objective,
        )
        print(f"ASR: {result.get('asr', 'N/A')}")
```
