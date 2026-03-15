---
sidebar_label: types
title: hackagent.risks.malicious_tool_invocation.types
---

Malicious Tool Invocation sub-types.

## MaliciousToolInvocationType Objects

```python
class MaliciousToolInvocationType(Enum)
```

Sub-types for Malicious Tool Invocation.

#### UNTRUSTED\_TOOL\_EXECUTION

Model executes or recommends untrusted third-party tools or plugins.

#### TOOL\_DATA\_EXFILTRATION

Tool interaction leads to data exfiltration.

#### TOOL\_PRIVILEGE\_ESCALATION

Tool actions exceed intended scope or permissions.

