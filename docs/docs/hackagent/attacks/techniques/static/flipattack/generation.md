---
sidebar_label: generation
title: hackagent.attacks.techniques.static.flipattack.generation
---

FlipAttack generation and execution module.

Generates flipped prompts by calling :meth:`FlipAttack.generate` on the
attack instance passed explicitly as `attack=`, then executes them against
the target model via HackAgent&#x27;s LLMRouter.

Result Tracking:
    Uses Tracker (passed via config[&quot;_tracker&quot;]) to add interaction traces
    per goal during generation and execution.

#### execute

```python
def execute(goals: List[str],
            agent_router: LLMRouter,
            config: Dict[str, Any],
            logger: logging.Logger,
            *,
            attack: Any = None) -> List[Dict]
```

Generate flipped prompts and execute them against target model.

**Arguments**:

- `goals` - List of harmful prompts to flip
- `agent_router` - Router for target model communication
- `config` - Configuration dictionary with flipattack_params
- `logger` - Logger instance
- `attack` - FlipAttack instance. Required for new callers. A leftover
  `config[&quot;_self&quot;]` is still read if `attack` is omitted;
  the pipeline no longer writes that key.
  

**Returns**:

  List of dicts with goal, flipped prompt, and response. No verdict.

