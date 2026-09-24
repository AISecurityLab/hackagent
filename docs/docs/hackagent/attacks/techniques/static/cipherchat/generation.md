---
sidebar_label: generation
title: hackagent.attacks.techniques.static.cipherchat.generation
---

CipherChat generation and execution module.

#### execute

```python
def execute(goals: List[str], agent_router: LLMRouter, config: Dict[str, Any],
            logger: logging.Logger) -> List[Dict[str, Any]]
```

Generate encoded CipherChat prompts and execute them on target model.

