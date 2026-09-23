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

Forward construction is ``BaseAttack(config, ctx)`` with
``run(goals) -&gt; list[AttackResult]``. ``config`` is an
:class:`~hackagent.attacks.config.AttackConfig` (or a plain dict). ``ctx``
is a :class:`~hackagent.attacks.ports.RunContext`. Pipeline stages may be
typed :class:`~hackagent.attacks.ports.Step` values or legacy dicts.

The orchestrator still instantiates shipped techniques as
``(config_dict, client, agent_router)`` until they migrate. That legacy
path, including ``client=`` as a keyword, remains supported.

Attack techniques are organized in:
    techniques/advprefix/attack.py    - AdvPrefixAttack
    techniques/static_template/attack.py - StaticTemplateAttack
    techniques/pair/attack.py         - PAIRAttack

Each technique:
- Extends BaseAttack
- Implements run(goals)
- Returns list[AttackResult]

The orchestration layer (attacks/orchestrator.py) handles server integration,
allowing techniques to focus solely on attack algorithms.

## BaseAttack Objects

```python
class BaseAttack(abc.ABC)
```

Abstract base class for attack technique implementations.

Provides common infrastructure that all attacks need:
- Configuration handling (typed :class:`~hackagent.attacks.config.AttackConfig` or dict)
- Run directory management
- Tracking initialization
- Pipeline execution (typed :class:`~hackagent.attacks.ports.Step` or legacy dicts)

Prefer ``BaseAttack(config, ctx)``. Logging handlers are not installed
here; interfaces own logging.

Subclasses:
1. Optionally set ``config_model`` to an AttackConfig subclass
2. Implement ``_validate_config()`` when extra validation is required
3. Implement ``_get_pipeline_steps()`` (``Step`` or legacy dict)
4. Implement ``run(goals)``

Shipped techniques still use the legacy ``(config, client, agent_router)``
constructor. Do not treat every technique as already migrated.

**Attributes**:

- `config` - Plain dict view of the attack config (``model_dump()`` when
  an AttackConfig was passed).
- `attack_config` - The AttackConfig instance, or None when a dict was passed.
- `ctx` - RunContext on the new seam, otherwise None.
- `backend` - Storage backend on the legacy path; None when ``ctx`` is set.
- `agent_router` - Target router. On the new seam this is ``ctx.target``.
- `logger` - Logger instance for this attack.
- `run_id` - Unique run identifier (``ctx.run_id``, else the config dict).
- `run_dir` - Output directory (``ctx.workspace.root``, else ``output_dir``).
- `coordinator` - TrackingCoordinator for unified tracking.
- `tracker` - StepTracker for execution tracking (alias for coordinator.step_tracker).

#### config\_model

Optional typed config model for the technique (Phase 4+).

#### \_\_init\_\_

```python
def __init__(config: Union[AttackConfig, Dict[str, Any]],
             ctx_or_client: Any = None,
             agent_router: Any = None,
             *,
             ctx: Optional[RunContext] = None,
             client: Any = None)
```

Initialize with ``(config, ctx)`` or legacy ``(config, client, agent_router)``.

Phase 4 seam: prefer ``BaseAttack(config, ctx)``. Existing techniques
and the orchestrator still pass ``(config_dict, client, agent_router)``
(including ``client=`` as a keyword); that path stays until Phase 5
migrates them. Logging handlers are no longer installed here —
interfaces own logging (D12).

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

Return attack-owned preflight model roles via ``AttackConfig.roles()``.

Prefer a technique ``config_model.roles()``. Fall back to
:func:`roles_from_paths` using ``attack_type``. Returning ``None``
is reserved for &quot;no opinion&quot; and should be rare after Phase 4.

#### run

```python
@abc.abstractmethod
def run(goals: Optional[Sequence[Union[Goal, str]]] = None,
        **kwargs: Any) -> List[AttackResult]
```

Execute the attack technique against *goals*.

Phase 4 signature is ``run(goals)``. Legacy ``**kwargs`` (including
passing goals as a kwarg) remains until Phase 5 migrates callers.

This method should:
1. Initialize tracking with self._initialize_coordinator()
2. Define pipeline with self._get_pipeline_steps() (dict or :class:`Step`)
3. Execute pipeline with self._execute_pipeline()
4. Finalize with coordinator.finalize_all_goals() and coordinator.finalize_pipeline()
5. Return results as ``list[AttackResult]`` (with optional ``verdict``)

**Arguments**:

- `goals` - Goals to attack (``Goal`` or raw strings).
- `**kwargs` - Technique-specific parameters (legacy).
  

**Returns**:

  A list of :class:`~hackagent.attacks.types.AttackResult` instances.

