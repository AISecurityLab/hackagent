---
sidebar_label: agent
title: hackagent.examples.openai_sdk.pc_tool_sandbox.agent
---

Sandboxed tool-using agent exposed via OpenAI-compatible endpoint.

Purpose:
- Simulate an agent that can access local files via tools.
- Keep access limited to a controlled `confidential/` folder.
- Provide a target endpoint for HackAgent attacks (including FlipAttack).

Run:
    export OPENROUTER_API_KEY=...
  python agent.py

#### ensure\_confidential\_seed\_files

```python
def ensure_confidential_seed_files() -> None
```

Create synthetic files for repeatable local security testing.

