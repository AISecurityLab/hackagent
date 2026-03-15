---
sidebar_label: lifelong
title: hackagent.attacks.techniques.autodan_turbo.lifelong
---

AutoDAN-Turbo lifelong phase: strategy-guided attacks with retrieval.

#### execute

```python
def execute(goals, config, client, agent_router, logger,
            strategy_library: StrategyLibrary) -> List[Dict]
```

Execute AutoDAN-Turbo lifelong strategy-guided attack loop.

Paper mapping:
- Retrieve strategies from the library using previous target response.
- Generate new attacker prompt conditioned on retrieved strategies.
- Query target and score response.
- When score improves, summarize prompt delta into a new strategy and add
it back into the library (lifelong self-improvement).

**Arguments**:

- `goals` - Attack goals to process.
- `config` - Full AutoDAN-Turbo configuration.
- `client` - Authenticated API client for role routers.
- `agent_router` - Target model router from framework.
- `logger` - Logger for lifecycle and per-epoch diagnostics.
- `strategy_library` - Warm-up-bootstrapped library used for retrieval/updates.
  

**Returns**:

  List of best result dictionaries per goal, including prompt/response,
  AutoDAN score, and success flag against ``break_score``.

