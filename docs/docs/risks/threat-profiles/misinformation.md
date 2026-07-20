---
sidebar_position: 8
---

# Misinformation Threat Profile

Tests whether the LLM produces factual fabrications or misinformation.

## Objective

`harmful_behavior`

## Recommended Datasets

### Primary Datasets
- **truthfulqa**: TruthfulQA for evaluating factual accuracy and misinformation

### Secondary Datasets
- **saladbench**: SaladBench for broader misinformation coverage

## Attack Techniques

### Primary Attacks
- **Static Template**: Template-based prompt construction

## Metrics

- truthfulness_score
- accuracy_score

## Usage Example

```python
from hackagent import HackAgent
from hackagent.risks.misinformation import MISINFORMATION_PROFILE

agent = HackAgent(endpoint="http://localhost:8080/chat", name="my-agent")

# Use profile recommendations
for attack in MISINFORMATION_PROFILE.primary_attacks:
    for dataset in MISINFORMATION_PROFILE.primary_datasets:
        attack_config = {
            "attack_type": attack.technique.lower(),
            "objective": MISINFORMATION_PROFILE.objective,
            "dataset": {"preset": dataset.preset},
        }
        results = agent.hack(attack_config=attack_config)
        print(f"Results: {results}")
```
