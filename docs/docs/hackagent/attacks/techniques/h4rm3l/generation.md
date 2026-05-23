---
sidebar_label: generation
title: hackagent.attacks.techniques.h4rm3l.generation
---

h4rm3l generation and execution module.

Compiles the decorator program, applies it to each goal prompt, and
sends the decorated prompt to the target model via AgentRouter.

#### execute

```python
def execute(goals: List[str], agent_router: AgentRouter,
            config: Dict[str, Any], logger: logging.Logger) -> List[Dict]
```

Generate decorated prompts and execute them against the target model.

**Arguments**:

- `goals` - List of goal strings to attack.
- `agent_router` - Router for target model communication.
- `config` - Configuration dictionary with ``h4rm3l_params``.
- `logger` - Logger instance.
  

**Returns**:

  List of result dicts with goal, decorated prompt, and response.

