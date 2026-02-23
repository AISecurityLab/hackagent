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

**Objective**: policy_violation

**Recommended Datasets**:
- **agentharm** (SECONDARY): Agentic tasks that exercise plugin/tool interactions

**Attack Techniques**:
- Baseline (PRIMARY): Template-based prompt construction

**Metrics**: asr, judge_score

## Usage Example

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
