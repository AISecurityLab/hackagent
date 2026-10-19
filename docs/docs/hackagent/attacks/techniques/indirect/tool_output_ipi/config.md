---
sidebar_label: config
title: hackagent.attacks.techniques.indirect.tool_output_ipi.config
---

Configuration for tool-output indirect prompt injection.

## ToolOutputIPIParams Objects

```python
class ToolOutputIPIParams(AttackParams)
```

How the poisoned tool result is built, and who sharpens it.

`attacker` is an optional role: when set, it refines the injection
payload across attempts. Without it a single payload is tried per goal
(`max_attempts` then has no effect, since nothing changes between
tries).

