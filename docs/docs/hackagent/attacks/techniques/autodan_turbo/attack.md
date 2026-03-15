---
sidebar_label: attack
title: hackagent.attacks.techniques.autodan_turbo.attack
---

AutoDAN-Turbo attack orchestrator — 3-step pipeline (WarmUp → Lifelong → Evaluation).

## AutoDANTurboAttack Objects

```python
class AutoDANTurboAttack(BaseAttack)
```

AutoDAN-Turbo: Lifelong agent for strategy self-exploration in jailbreaking LLMs.

Three-phase pipeline:
1. WarmUp — free exploration to bootstrap a strategy library
2. Lifelong — strategy-guided attacks with retrieval + summarization
3. Evaluation — multi-judge scoring for consistent metrics

#### \_\_init\_\_

```python
def __init__(config=None, client=None, agent_router=None)
```

Initialize AutoDAN-Turbo attack with merged defaults.

**Arguments**:

- `config` - Optional user overrides for default config.
- `client` - Authenticated API client (required).
- `agent_router` - Router to the target model (required).
  

**Returns**:

  None.
  

**Raises**:

- `ValueError` - If ``client`` or ``agent_router`` are missing.

#### run

```python
@with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
def run(goals: List[str]) -> List[Dict[str, Any]]
```

Execute full 3-step AutoDAN-Turbo pipeline.

Pipeline mapping to paper/integration:
1) WarmUp: free exploration + strategy library bootstrap
2) Lifelong: retrieval-guided attack with online strategy growth
3) Evaluation: hackagent multi-judge scoring harmonization

**Arguments**:

- `goals` - List of malicious goals to attack.
  

**Returns**:

  Final per-goal result list, enriched with attack and judge metrics.
  

**Raises**:

- `Exception` - Re-raises any runtime failure after coordinator finalization.

