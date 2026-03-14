---
sidebar_position: 1
---

# Prompt Injection Threat Profile

Tests whether injected instructions override system prompts.

## Objective

`jailbreak`

## Recommended Datasets

### Primary Datasets
- **advbench**: 520 adversarial goals covering injection scenarios
- **harmbench_contextual**: Contextual prompts requiring instruction override
- **prompt_injections**: 662 prompt injection samples for direct PI testing (deepset)

### Secondary Datasets
- **strongreject**: Forbidden prompts to test injection guardrails

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
from hackagent.risks.prompt_injection import PROMPT_INJECTION_PROFILE

agent = HackAgent(endpoint="http://localhost:8080/chat", name="my-agent")

# Use profile recommendations
for attack in PROMPT_INJECTION_PROFILE.primary_attacks:
    for dataset in PROMPT_INJECTION_PROFILE.primary_datasets:
        result = agent.attack(
            attack_type=attack.technique.lower(),
            dataset=dataset.preset,
            objective=PROMPT_INJECTION_PROFILE.objective,
        )
        print(f"ASR: {result.get('asr', 'N/A')}")
```
