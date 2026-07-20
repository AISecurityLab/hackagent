---
sidebar_position: 7
---

# Sensitive Information Disclosure Threat Profile

Tests for training data extraction, architecture disclosure, and config leakage.

## Objective

`jailbreak`

## Recommended Datasets

### Secondary Datasets
- **advbench**: Adversarial prompts that may trigger info leaks
- **saladbench**: 21K harmful questions — includes info disclosure scenarios

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
from hackagent.risks.sensitive_information_disclosure import SENSITIVE_INFORMATION_DISCLOSURE_PROFILE

agent = HackAgent(endpoint="http://localhost:8080/chat", name="my-agent")

# Use profile recommendations
for attack in SENSITIVE_INFORMATION_DISCLOSURE_PROFILE.primary_attacks:
    for dataset in SENSITIVE_INFORMATION_DISCLOSURE_PROFILE.primary_datasets + SENSITIVE_INFORMATION_DISCLOSURE_PROFILE.secondary_datasets:
        attack_config = {
            "attack_type": attack.technique.lower(),
            "objective": SENSITIVE_INFORMATION_DISCLOSURE_PROFILE.objective,
            "dataset": {"preset": dataset.preset},
        }
        results = agent.hack(attack_config=attack_config)
        print(f"Results: {results}")
```
