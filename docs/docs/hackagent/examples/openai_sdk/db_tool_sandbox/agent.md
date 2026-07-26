---
sidebar_label: agent
title: hackagent.examples.openai_sdk.db_tool_sandbox.agent
---

Sandboxed DB tool-using agent exposed via OpenAI-compatible endpoint.

Purpose:
- Simulate an LLM target with real DB access through explicit tools.
- Keep the setup local and reproducible (SQLite file).
- Provide a target endpoint for HackAgent red-team attacks.

Run:
  python agent.py

#### ensure\_seed\_database

```python
def ensure_seed_database() -> None
```

Create a local SQLite DB with synthetic test data.

