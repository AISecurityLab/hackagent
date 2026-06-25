---
sidebar_label: base
title: hackagent.attacks.techniques.base
---

Base class for attack technique implementations.

This module provides BaseAttack, the abstract base class for all attack
technique implementations. Techniques focus purely on attack algorithms
and evaluation, without knowledge of server integration.

Architecture:
    HackAgent → AttackOrchestrator → BaseAttack → Pipeline stages

Attack techniques are organized in:
    techniques/advprefix/attack.py    - AdvPrefixAttack
    techniques/baseline/attack.py - BaselineAttack
    techniques/pair/attack.py         - PAIRAttack

Each technique:
- Extends BaseAttack
- Implements run() method with attack logic
- Uses objectives from attacks/objectives/ for evaluation
- Returns results in appropriate format (DataFrame, dict, etc.)

The orchestration layer (attacks/orchestrator.py) handles server integration,
allowing techniques to focus solely on attack algorithms.

## BaseAttack Objects

```python
class BaseAttack(abc.ABC)
```

Abstract base class for attack technique implementations.

Provides common infrastructure that all attacks need:
- Configuration management (merging with defaults)
- Logging setup
- Run directory management
- Tracking initialization
- Parent result creation
- Pipeline execution framework

Subclasses only need to:
1. Define DEFAULT_CONFIG in their module
2. Implement _validate_config() for specific validation
3. Implement _get_pipeline_steps() to define their attack pipeline
4. Implement _build_step_args() if custom argument handling needed

**Attributes**:

- `config` - Merged configuration dictionary
- `client` - Authenticated HackAgent client
- `agent_router` - Target agent router for queries
- `logger` - Logger instance for this attack
- `run_id` - Unique run identifier
- `run_dir` - Output directory for this run
- `coordinator` - TrackingCoordinator for unified tracking
- `tracker` - StepTracker for execution tracking (alias for coordinator.step_tracker)

#### \_\_init\_\_

```python
def __init__(config: Dict[str, Any],
             client: Any = None,
             agent_router: Any = None,
             **kwargs)
```

Initialize attack implementation with common setup.

**Arguments**:

- `config` - Attack configuration (will be merged with DEFAULT_CONFIG)
- `client` - Authenticated HackAgent client
- `agent_router` - Target agent router
- `**kwargs` - Additional technique-specific parameters

#### get\_effective\_model\_roles

```python
@classmethod
def get_effective_model_roles(
    cls,
    attack_config: Dict[str, Any],
    *,
    goal_labels_by_index: Optional[Dict[int, Dict[str, str]]] = None
) -> Optional[List[Dict[str, Any]]]
```

Return attack-owned preflight model roles, or ``None`` for fallback mapping.

The orchestrator consumes this hook before using its legacy static role map.
Each returned item should be a dict with:

- ``role``: logical role label (e.g. ``judge``)
- ``config``: model/router config dict for that role
- ``required`` (optional): whether this role must pass preflight

Returning ``None`` delegates role discovery to orchestrator fallback logic.
Returning ``[]`` means no attack-specific model roles are required.

#### run

```python
@abc.abstractmethod
def run(**kwargs) -> Any
```

Execute the attack technique.

This method should:
1. Initialize tracking with self._initialize_coordinator()
2. Define pipeline with self._get_pipeline_steps()
3. Execute pipeline with self._execute_pipeline()
4. Finalize with coordinator.finalize_all_goals() and coordinator.finalize_pipeline()
5. Return results

**Arguments**:

- `**kwargs` - Technique-specific parameters (e.g., goals, prompts)
  

**Returns**:

  Attack results (format varies by implementation)

