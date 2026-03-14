---
sidebar_position: 10
---

# Malicious Tool Invocation Threat Profile

Tests for untrusted plugin execution, data exfiltration, and privilege escalation via plugins.

## Objective

`policy_violation`

## Recommended Datasets

### Secondary Datasets
- **agentharm**: Agentic tasks that exercise plugin/tool interactions

## Attack Techniques

### Primary Attacks
- **Baseline**: Template-based prompt construction

## Metrics

- asr
- judge_score

## Usage Example

```python
from hackagent import HackAgent
from hackagent.risks.malicious_tool_invocation import MALICIOUS_TOOL_INVOCATION_PROFILE

agent = HackAgent(endpoint="http://localhost:8080/chat", name="my-agent")

# Use profile recommendations
for attack in MALICIOUS_TOOL_INVOCATION_PROFILE.primary_attacks:
    for dataset in MALICIOUS_TOOL_INVOCATION_PROFILE.primary_datasets + MALICIOUS_TOOL_INVOCATION_PROFILE.secondary_datasets:
        result = agent.attack(
            attack_type=attack.technique.lower(),
            dataset=dataset.preset,
            objective=MALICIOUS_TOOL_INVOCATION_PROFILE.objective,
        )
        print(f"ASR: {result.get('asr', 'N/A')}")
```
