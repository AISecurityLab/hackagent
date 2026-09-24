---
sidebar_label: generation
title: hackagent.attacks.techniques.static.h4rm3l.generation
---

h4rm3l generation and execution module.

Compiles the decorator program, applies it to each goal prompt, and
sends the decorated prompt to the target model via LLMRouter.

#### execute

```python
def execute(goals: List[str],
            agent_router: LLMRouter,
            config: Dict[str, Any],
            logger: logging.Logger,
            *,
            decorator_llm_router: Optional[LLMRouter] = None,
            decorator_llm_key: Optional[str] = None) -> List[Dict]
```

Generate decorated prompts and execute them against the target model.

**Arguments**:

- `goals` - List of goal strings to attack.
- `agent_router` - Router for target model communication.
- `config` - Configuration dictionary with `h4rm3l_params`.
- `decorator_llm_router` - Optional explicit router for LLM-assisted
  decorators. When omitted, generation resolves `decorator_llm`
  from `config`.
- `logger` - Logger instance.
  

**Returns**:

  List of result dicts with goal, decorated prompt, and response.

