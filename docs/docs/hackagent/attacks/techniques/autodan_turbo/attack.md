---
sidebar_label: attack
title: hackagent.attacks.techniques.autodan_turbo.attack
---

AutoDAN-Turbo orchestrator — WarmUp → Lifelong → shared LLM-judge evaluation.

## AutoDANTurboAttack Objects

```python
class AutoDANTurboAttack(BaseAttack)
```

AutoDAN-Turbo: Lifelong agent for strategy self-exploration in jailbreaking LLMs.

Three-phase pipeline:
1. WarmUp — free exploration to bootstrap a strategy library
2. Lifelong — strategy-guided attacks with retrieval + summarization
3. Evaluation — shared LLM-judge result finalization

#### \_\_init\_\_

```python
def __init__(config=None,
             ctx_or_client=None,
             agent_router=None,
             *,
             ctx: Optional[RunContext] = None,
             client=None)
```

Initialize AutoDAN-Turbo with ``(config, ctx)`` or legacy args.

On the new seam ``ctx.models`` and ``ctx.judge`` are stored on the
config for warm-up and lifelong, and the strategy library is
written under ``ctx.workspace``. This class does not read
``_suppress_run_status_updates``. ``AutoDANTurboConfig`` still
subclasses :class:`~hackagent.attacks.techniques.config.ConfigBase`.
The legacy constructor is obsolete for new code.

#### run

```python
def run(goals: Optional[List[str]] = None, **kwargs) -> List[AttackResult]
```

Execute full AutoDAN-Turbo pipeline.

Pipeline mapping to paper/integration:
1) WarmUp: free exploration + strategy library bootstrap
2) Lifelong: retrieval-guided attack with online strategy growth
3) Evaluation: shared LLM-judge normalization and success finalization

**Arguments**:

- `goals` - List of malicious goals to attack.
  

**Returns**:

  Final per-goal result list, enriched with LLM judge outputs.
  

**Raises**:

- `Exception` - Re-raises any runtime failure after coordinator finalization.

