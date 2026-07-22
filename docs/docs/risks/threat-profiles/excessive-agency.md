---
sidebar_position: 9
---

# Excessive Agency Threat Profile

Tests whether the LLM performs actions exceeding its intended scope.

## Objective

`policy_violation`

## Recommended Datasets

### Primary Datasets
- **agentharm**: AgentHarm dataset for evaluating excessive agency in tool use

### Secondary Datasets
- **agentharm_benign**: Benign agent scenarios to establish baseline behavior

## Attack Techniques

### Primary Attacks
- **Static Template**: Template-based prompt construction

## Metrics

- asr
- judge_score

## Usage Example

```python
from hackagent import HackAgent
from hackagent.risks.excessive_agency import EXCESSIVE_AGENCY_PROFILE

agent = HackAgent(endpoint="http://localhost:8080/chat", name="my-agent")

# Use profile recommendations
for attack in EXCESSIVE_AGENCY_PROFILE.primary_attacks:
    for dataset in EXCESSIVE_AGENCY_PROFILE.primary_datasets:
        attack_config = {
            "attack_type": attack.technique.lower(),
            "objective": EXCESSIVE_AGENCY_PROFILE.objective,
            "dataset": {"preset": dataset.preset},
        }
        results = agent.hack(attack_config=attack_config)
        print(f"Results: {results}")
```
