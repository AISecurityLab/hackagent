---
sidebar_label: generation
title: hackagent.attacks.techniques.cipherchat.generation
---

CipherChat generation and execution module.

#### execute

```python
def execute(goals: List[str], agent_router: AgentRouter, config: Dict[str,
                                                                      Any],
            logger: logging.Logger) -> List[Dict[str, Any]]
```

Generate encoded CipherChat prompts and execute them on target model.

