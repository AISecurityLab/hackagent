---
sidebar_position: 4
---

# System Prompt Leakage

Tests whether the LLM reveals sensitive details from its system prompt, such as credentials, internal instructions, or guardrails.

## Sub-types

- **Secrets and Credentials**: Reveals API keys, database credentials, or system architecture from the prompt.
- **Instructions**: Discloses internal instructions, rules, or operational procedures.
- **Guard Exposure**: Exposes guard mechanisms, rejection rules, or filtering criteria.
- **Permissions and Roles**: Reveals role-based permissions, access controls, or internal configurations.

## Threat Profile

**Objective**: `jailbreak`

### Recommended Datasets

**Secondary**
- **advbench**: Adversarial goals that may trigger system prompt disclosure

### Attack Techniques

**Primary**
- **Static Template**: Template-based prompt injection
- **PAIR**: Iterative refinement for bypass discovery

**Secondary**
- **AdvPrefix**: Adversarial prefix optimisation

### Metrics

- asr
- judge_score

## Usage

### Instantiate the Vulnerability

```python
from hackagent.risks import SystemPromptLeakage
from hackagent.risks.system_prompt_leakage.types import SystemPromptLeakageType

# Use all sub-types
vuln = SystemPromptLeakage()

# Or specify particular sub-types
vuln = SystemPromptLeakage(types=[
    SystemPromptLeakageType.SECRETS_AND_CREDENTIALS.value,
    SystemPromptLeakageType.GUARD_EXPOSURE.value,
])
```

### Run an Evaluation Campaign

```python
from hackagent import HackAgent
from hackagent.risks.system_prompt_leakage import SYSTEM_PROMPT_LEAKAGE_PROFILE

agent = HackAgent(endpoint="http://localhost:8080/chat", name="my-agent")

# Profile techniques use display casing (e.g. "StaticTemplate");
# HackAgent.hack() expects the registered snake_case attack_type key.
ATTACK_TYPE_KEYS = {"StaticTemplate": "static_template", "PAIR": "pair"}

# Use profile recommendations
for attack in SYSTEM_PROMPT_LEAKAGE_PROFILE.primary_attacks:
    for dataset in SYSTEM_PROMPT_LEAKAGE_PROFILE.primary_datasets + SYSTEM_PROMPT_LEAKAGE_PROFILE.secondary_datasets:
        attack_config = {
            "attack_type": ATTACK_TYPE_KEYS[attack.technique],
            "objective": SYSTEM_PROMPT_LEAKAGE_PROFILE.objective,
            "dataset": {"preset": dataset.preset},
        }
        results = agent.hack(attack_config=attack_config)
        print(f"Results: {results}")
```
