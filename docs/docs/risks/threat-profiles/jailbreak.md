---
sidebar_position: 2
---

# Jailbreak Threat Profile

Tests resistance to multi-turn, roleplay, encoding, and authority-based bypass.

## Objective

`jailbreak`

## Recommended Datasets

### Primary Datasets
- **strongreject**: 324 forbidden prompts designed for jailbreak evaluation
- **harmbench**: 200 harmful behaviors for bypass testing
- **advbench**: 520 adversarial goals for jailbreak attacks
- **jailbreakbench**: 100 curated misuse behaviours from NeurIPS 2024 benchmark

### Secondary Datasets
- **simplesafetytests**: 100 clear-cut harmful prompts as baseline
- **donotanswer**: 939 refusal questions for comprehensive coverage
- **saladbench_attack**: 5K attack-enhanced prompts with jailbreak methods

## Attack Techniques

### Primary Attacks
- **Baseline**: Template-based attack
- **PAIR**: Iterative refinement
- **AdvPrefix**: Adversarial prefix optimisation

## Metrics

- asr
- judge_score

## Usage Example

```python
from hackagent import HackAgent
from hackagent.risks.jailbreak import JAILBREAK_PROFILE

agent = HackAgent(endpoint="http://localhost:8080/chat", name="my-agent")

# Use profile recommendations
for attack in JAILBREAK_PROFILE.primary_attacks:
    for dataset in JAILBREAK_PROFILE.primary_datasets:
        result = agent.attack(
            attack_type=attack.technique.lower(),
            dataset=dataset.preset,
            objective=JAILBREAK_PROFILE.objective,
        )
        print(f"ASR: {result.get('asr', 'N/A')}")
```
