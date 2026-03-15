---
sidebar_label: router_factory
title: hackagent.attacks.shared.router_factory
---

Shared router factory for attack modules.

This module provides a unified factory function for creating AgentRouter
instances from configuration dictionaries. It eliminates the duplicated
~30-line router initialization pattern found across:

- advprefix/generate.py  (_initialize_generation_router)
- advprefix/evaluators.py (BaseEvaluator.__init__ router setup)
- pair/attack.py          (_initialize_attacker_router)

All three follow the same pattern: extract endpoint/model_id, handle API
key (env var fallback), build operational_config, create AgentRouter,
validate registry, extract registration key.

Usage:
    from hackagent.attacks.shared.router_factory import create_router

    router, reg_key = create_router(
        client=client,
        config=&#123;
            &quot;identifier&quot;: &quot;ollama/llama3&quot;,
            &quot;endpoint&quot;: &quot;http://localhost:11434/v1&quot;,
            &quot;max_new_tokens&quot;: 500,
            &quot;temperature&quot;: 0.7,
        &#125;,
        logger=logger,
        router_name=&quot;attacker&quot;,
    )

#### create\_router

```python
def create_router(
        backend: Any,
        config: Dict[str, Any],
        logger: Optional[logging.Logger] = None,
        router_name: Optional[str] = None) -> Tuple[AgentRouter, str]
```

Create an AgentRouter from a configuration dictionary.

**Arguments**:

- `backend` - StorageBackend providing default API key.
- `config` - Configuration dictionary (identifier, endpoint, agent_type, api_key etc.)
- `logger` - Logger instance.
- `router_name` - Human-readable name for logging.
  

**Returns**:

  Tuple of (AgentRouter, registration_key).

