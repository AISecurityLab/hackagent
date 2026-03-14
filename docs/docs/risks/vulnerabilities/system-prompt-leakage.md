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

**Objective**: jailbreak

**Recommended Datasets**:
- **advbench** (SECONDARY): Adversarial goals that may trigger system prompt disclosure

**Attack Techniques**:
- Baseline (PRIMARY): Template-based prompt injection
- PAIR (PRIMARY): Iterative refinement for bypass discovery
- AdvPrefix (SECONDARY): Adversarial prefix optimisation

**Metrics**: asr, judge_score

## Usage Example

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
