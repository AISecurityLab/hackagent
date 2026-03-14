---
sidebar_position: 3
---

# Input Manipulation Attack Threat Profile

Tests for SQL injection, command injection, and shell escape sequences.

## Objective

`jailbreak`

## Recommended Datasets

### Secondary Datasets
- **wmdp_cyber**: Cybersecurity knowledge covering SQL injection and command injection techniques

## Attack Techniques

### Primary Attacks
- **Baseline**: Template-based prompt injection
- **PAIR**: Iterative refinement for bypass discovery

### Secondary Attacks
- **AdvPrefix**: Adversarial prefix optimisation

## Metrics

- asr
- judge_score

## Usage Example

```python
from hackagent import HackAgent
from hackagent.risks.input_manipulation_attack import INPUT_MANIPULATION_ATTACK_PROFILE

agent = HackAgent(endpoint="http://localhost:8080/chat", name="my-agent")

# Use profile recommendations
for attack in INPUT_MANIPULATION_ATTACK_PROFILE.primary_attacks:
    for dataset in INPUT_MANIPULATION_ATTACK_PROFILE.primary_datasets + INPUT_MANIPULATION_ATTACK_PROFILE.secondary_datasets:
        result = agent.attack(
            attack_type=attack.technique.lower(),
            dataset=dataset.preset,
            objective=INPUT_MANIPULATION_ATTACK_PROFILE.objective,
        )
        print(f"ASR: {result.get('asr', 'N/A')}")
```
