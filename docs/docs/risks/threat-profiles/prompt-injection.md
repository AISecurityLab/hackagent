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
- **Static Template**: Template-based prompt injection
- **PAIR**: Iterative refinement for bypass discovery

### Secondary Attacks
- **AdvPrefix**: Adversarial prefix optimisation

## Indirect Injection

When the target system uses retrieval, add an indirect prompt injection campaign to measure exposure to poisoned knowledge-base content.

- Recommended technique: `rag`
- Focus metric: `asr` with retrieval-hit diagnostics
- Suggested tuning baseline: `chunk_size=1400`, `chunk_overlap=250`, `top_k=5`

Reference technique guide: [RAG Attack](../../attacks/rag.md).

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
        attack_config = {
            "attack_type": attack.technique.lower(),
            "objective": PROMPT_INJECTION_PROFILE.objective,
            "dataset": {"preset": dataset.preset},
        }
        results = agent.hack(attack_config=attack_config)
        print(f"Results: {results}")
```
