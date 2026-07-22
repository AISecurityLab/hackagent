---
sidebar_position: 5
---

# Model Evasion Threat Profile

Tests whether adversarial examples can evade the model's safety mechanisms.

## Objective

`jailbreak`

## Recommended Datasets

### Primary Datasets
- **advbench**: Adversarial benchmarks for evaluating evasion resistance

### Secondary Datasets
- **xstest**: XSTest for adversarial prompt detection

## Attack Techniques

### Primary Attacks
- **Static Template**: Template-based prompt injection
- **PAIR**: Iterative refinement for bypass discovery

### Secondary Attacks
- **AdvPrefix**: Adversarial prefix optimisation

## Metrics

- asr
- judge_score

## Usage Example

```python
from hackagent import HackAgent
from hackagent.risks.model_evasion import MODEL_EVASION_PROFILE

agent = HackAgent(endpoint="http://localhost:8080/chat", name="my-agent")

# Use profile recommendations
for attack in MODEL_EVASION_PROFILE.primary_attacks:
    for dataset in MODEL_EVASION_PROFILE.primary_datasets:
        attack_config = {
            "attack_type": attack.technique.lower(),
            "objective": MODEL_EVASION_PROFILE.objective,
            "dataset": {"preset": dataset.preset},
        }
        results = agent.hack(attack_config=attack_config)
        print(f"Results: {results}")
```
