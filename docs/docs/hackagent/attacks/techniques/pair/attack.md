---
sidebar_label: attack
title: hackagent.attacks.techniques.pair.attack
---

PAIR attack implementation.

Implements the Prompt Automatic Iterative Refinement (PAIR) attack using
an attacker LLM to iteratively refine jailbreak prompts.

Result Tracking:
    Uses TrackingCoordinator to manage both pipeline-level StepTracker
    and per-goal Tracker. The coordinator handles goal lifecycle,
    crash-safe finalization, and summary logging.

## PAIRAttack Objects

```python
class PAIRAttack(BaseAttack)
```

PAIR (Prompt Automatic Iterative Refinement) attack.

Uses an attacker LLM to generate and iteratively refine adversarial
prompts based on target model responses and judge feedback.

#### \_\_init\_\_

```python
def __init__(config: Optional[Dict[str, Any]] = None,
             client: Optional[AuthenticatedClient] = None,
             agent_router: Optional[AgentRouter] = None)
```

Initialize PAIR attack.

#### run

```python
@with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
def run(goals: List[str]) -> List[Dict[str, Any]]
```

Execute PAIR attack on goals.

Uses TrackingCoordinator to manage both pipeline-level and
per-goal result tracking through a single unified interface.

**Arguments**:

- `goals` - List of harmful goals to test
  

**Returns**:

  List of attack results with scores

