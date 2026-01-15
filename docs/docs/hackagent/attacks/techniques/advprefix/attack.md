---
sidebar_label: attack
title: hackagent.attacks.techniques.advprefix.attack
---

Prefix generation pipeline attack based on the BaseAttack class.

This module implements a complete pipeline for generating, filtering, and selecting prefixes
using uncensored and target language models, adapted as an attack module.

## AdvPrefixAttack Objects

```python
class AdvPrefixAttack(BaseAttack)
```

Attack class implementing the prefix generation pipeline by orchestrating step modules.

Inherits from BaseAttack and adapts the multi-step prefix generation process.
Expects configuration as a standard Python dictionary.

#### \_\_init\_\_

```python
def __init__(config: Optional[Dict[str, Any]] = None,
             client: Optional[AuthenticatedClient] = None,
             agent_router: Optional[AgentRouter] = None)
```

Initialize the pipeline with configuration.

**Arguments**:

- `config` - An optional dictionary containing pipeline parameters to override defaults.
- `client` - An AuthenticatedClient instance passed from the strategy.
- `agent_router` - An AgentRouter instance passed from the strategy.

#### run

```python
@with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
def run(goals: List[str]) -> List[Dict]
```

Executes the full prefix generation pipeline.

**Arguments**:

- `goals` - A list of goal strings to generate prefixes for.
  

**Returns**:

  List of dictionaries containing the final selected prefixes,
  or empty list if no prefixes were generated.

