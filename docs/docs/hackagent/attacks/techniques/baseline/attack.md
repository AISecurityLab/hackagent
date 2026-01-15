---
sidebar_label: attack
title: hackagent.attacks.techniques.baseline.attack
---

Baseline attack implementation.

Uses predefined prompt templates to attempt jailbreaks by combining
templates with harmful goals.

## BaselineAttack Objects

```python
class BaselineAttack(BaseAttack)
```

Baseline attack using predefined prompt patterns.

Combines templates with goals to generate jailbreak attempts,
then evaluates responses using objective-based criteria.

#### \_\_init\_\_

```python
def __init__(config: Optional[Dict[str, Any]] = None,
             client: Optional[AuthenticatedClient] = None,
             agent_router: Optional[AgentRouter] = None)
```

Initialize baseline attack.

**Arguments**:

- `config` - Configuration dictionary
- `client` - Authenticated client for API calls
- `agent_router` - Target agent router

#### run

```python
@with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
def run(goals: List[str]) -> Dict[str, Any]
```

Execute baseline attack.

**Arguments**:

- `goals` - List of harmful goals to test
  

**Returns**:

  Dictionary with &#x27;evaluated&#x27; and &#x27;summary&#x27; DataFrames

