---
sidebar_label: generation
title: hackagent.attacks.techniques.baseline.generation
---

Generation module for the Baseline attack.

Sends each goal directly to the target model without any transformation.

#### execute

```python
def execute(goals: List[str],
            agent_router: AgentRouter,
            config: Dict[str, Any],
            logger: logging.Logger,
            goal_tracker: Optional[Tracker] = None) -> List[Dict[str, Any]]
```

Send each goal directly to the target model and collect responses.

**Arguments**:

- `goals` - List of goal strings to send as-is.
- `agent_router` - Target agent router.
- `config` - Configuration dictionary.
- `logger` - Logger instance.
- `goal_tracker` - Optional Tracker for per-goal result tracking.
  

**Returns**:

  List of dicts with keys: goal, goal_index, attack_prompt, completion,
  response_length, and optionally guardrail_blocked or error.

