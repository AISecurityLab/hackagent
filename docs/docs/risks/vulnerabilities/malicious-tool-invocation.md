---
sidebar_position: 10
---

# Malicious Tool Invocation

Tests for risks from untrusted tool execution, data exfiltration through tool interactions, and tool privilege escalation.

## Sub-types

- **Untrusted Tool Execution**: Model executes or recommends untrusted third-party tools or plugins.
- **Tool Data Exfiltration**: Tool interaction leads to data exfiltration.
- **Tool Privilege Escalation**: Tool actions exceed intended scope or permissions.

## Threat Profile

**Objective**: `policy_violation`

:::note Objective vs. goals
The `objective` above selects the **scoring rubric** for a run — it is one of a
fixed set of built-in names, not something you write. The `goals` you pass to an
attack are separate free-text strings that you author yourself. See
[Goals vs. objective](../../attacks/index.mdx#goals-vs-objective).
:::

### Recommended Datasets

**Secondary**
- **agentharm**: Agentic tasks that exercise plugin/tool interactions

### Attack Techniques

**Primary**
- **Static Template**: Template-based prompt construction

### Metrics

- asr
- judge_score

## Usage

### Instantiate the Vulnerability

```python
from hackagent.risks import MaliciousToolInvocation
from hackagent.risks.malicious_tool_invocation.types import MaliciousToolInvocationType

# Use all sub-types
vuln = MaliciousToolInvocation()

# Or specify particular sub-types
vuln = MaliciousToolInvocation(types=[
    MaliciousToolInvocationType.UNTRUSTED_TOOL_EXECUTION.value,
    MaliciousToolInvocationType.TOOL_PRIVILEGE_ESCALATION.value,
])
```

### Run an Evaluation Campaign

```python
from hackagent import HackAgent
from hackagent.risks.malicious_tool_invocation import MALICIOUS_TOOL_INVOCATION_PROFILE

agent = HackAgent(endpoint="http://localhost:8080/chat", name="my-agent")

# Use profile recommendations
for attack in MALICIOUS_TOOL_INVOCATION_PROFILE.primary_attacks:
    for dataset in MALICIOUS_TOOL_INVOCATION_PROFILE.primary_datasets + MALICIOUS_TOOL_INVOCATION_PROFILE.secondary_datasets:
        attack_config = {
            "attack_type": "static_template",  # attack.technique is "StaticTemplate"
            "objective": MALICIOUS_TOOL_INVOCATION_PROFILE.objective,
            "dataset": {"preset": dataset.preset},
        }
        results = agent.hack(attack_config=attack_config)
        print(f"Results: {results}")
```
