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
- **Baseline**: Template-based prompt construction

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
        result = agent.attack(
            attack_type=attack.technique.lower(),
            dataset=dataset.preset,
            objective=MISINFORMATION_PROFILE.objective,
        )
        print(f"Metrics: {result}")
```
