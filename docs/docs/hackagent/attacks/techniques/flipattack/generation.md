---
sidebar_label: generation
title: hackagent.attacks.techniques.flipattack.generation
---

FlipAttack generation and execution module.

Generates flipped prompts by calling :meth:`FlipAttack.generate` on the
attack instance passed via ``config[&quot;_self&quot;]``, then executes them against
the target model via HackAgent&#x27;s AgentRouter.

Result Tracking:
    Uses Tracker (passed via config[&quot;_tracker&quot;]) to add interaction traces
    per goal during generation and execution.

#### execute

```python
def execute(goals: List[str], agent_router: AgentRouter,
            config: Dict[str, Any], logger: logging.Logger) -> List[Dict]
```

Generate flipped prompts and execute them against target model.

**Arguments**:

- `goals` - List of harmful prompts to flip
- `agent_router` - Router for target model communication
- `config` - Configuration dictionary with flipattack_params
- `logger` - Logger instance
  

**Returns**:

  List of dicts with goal, flipped prompt, and response

