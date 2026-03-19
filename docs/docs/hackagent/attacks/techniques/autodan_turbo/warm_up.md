---
sidebar_label: warm_up
title: hackagent.attacks.techniques.autodan_turbo.warm_up
---

AutoDAN-Turbo warm-up phase: free exploration + strategy library building.

#### execute

```python
def execute(goals, config, client, agent_router,
            logger) -> Tuple[StrategyLibrary, List[Dict]]
```

Execute AutoDAN-Turbo warm-up end to end.

Paper mapping:
1) Free exploration loop where attacker generates candidate jailbreak
prompts, target responds, scorer assigns 1-10 score.
2) ``build_from_warm_up_log`` behavior where min/max-scored prompt pairs
are summarized into reusable strategies added to the strategy library.

**Arguments**:

- `goals` - List of attack goals (malicious requests).
- `config` - Full AutoDAN-Turbo configuration.
- `client` - Authenticated client used to create attacker/scorer/summarizer routers.
- `agent_router` - Router connected to the target model.
- `logger` - Logger used for phase-level diagnostics.
  

**Returns**:

  Tuple ``(strategy_library, attack_log)`` where:
  - ``strategy_library`` is a populated ``StrategyLibrary`` instance for lifelong phase.
  - ``attack_log`` is list of per-attempt records (goal, prompt, response, score, iteration metadata).

