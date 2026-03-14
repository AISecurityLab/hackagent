---
sidebar_position: 4
---

# System Prompt Leakage Threat Profile

Tests whether the model leaks system prompts, secrets, or guard configurations.

## Objective

`jailbreak`

## Recommended Datasets

### Secondary Datasets
- **advbench**: Adversarial goals that may trigger system prompt disclosure

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
from hackagent.risks.system_prompt_leakage import SYSTEM_PROMPT_LEAKAGE_PROFILE

agent = HackAgent(endpoint="http://localhost:8080/chat", name="my-agent")

# Use profile recommendations
for attack in SYSTEM_PROMPT_LEAKAGE_PROFILE.primary_attacks:
    for dataset in SYSTEM_PROMPT_LEAKAGE_PROFILE.primary_datasets + SYSTEM_PROMPT_LEAKAGE_PROFILE.secondary_datasets:
        result = agent.attack(
            attack_type=attack.technique.lower(),
            dataset=dataset.preset,
            objective=SYSTEM_PROMPT_LEAKAGE_PROFILE.objective,
        )
        print(f"ASR: {result.get('asr', 'N/A')}")
```
