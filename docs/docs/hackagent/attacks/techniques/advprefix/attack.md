---
sidebar_label: attack
title: hackagent.attacks.techniques.advprefix.attack
---

Prefix generation pipeline attack based on the BaseAttack class.

This module implements a complete pipeline for generating, filtering, and selecting prefixes
using uncensored and target language models, adapted as an attack module.

Result Tracking:
    Uses TrackingCoordinator to manage both pipeline-level StepTracker
    and per-goal Tracker. The coordinator handles goal lifecycle,
    crash-safe finalization, and data enrichment (result_id injection).

## AdvPrefixAttack Objects

```python
class AdvPrefixAttack(BaseAttack)
```

AdvPrefix attack — adversarial prefix generation pipeline.

Implements a multi-stage pipeline that:

1. **Generation** — uses an uncensored attacker LLM to produce
candidate adversarial prefixes for each harmless meta-prompt.
Prefixes are filtered by cross-entropy (`max_ce`) and token
segment count before being passed downstream.
2. **Execution** — appends each surviving prefix to the target model
prompt and collects completions (`n_samples` per prefix).
3. **Selection** — on the new seam, `ctx.judge.evaluate` scores each
completion and the top-`n_prefixes_per_goal` prefixes per goal
are kept. That is the only post-hoc path that attaches a verdict.
The legacy constructor still uses :class:`EvaluationPipeline`.

The class delegates stage logic to dedicated sub-modules:

* :mod:`~hackagent.attacks.techniques.advprefix.generate`
(:class:`PrefixGenerationPipeline`) for steps 1 and internal
filtering.
* :mod:`~hackagent.attacks.techniques.advprefix.completions` for
step 2.
* :meth:`_evaluate_and_select` for step 3 (`ctx.judge.evaluate`, or
:class:`EvaluationPipeline` on the legacy constructor).

Tracking is managed by
:class:`~hackagent.tracking.TrackingCoordinator`; goal
:class:`~hackagent.tracking.Tracker` instances and a pipeline
:class:`~hackagent.tracking.StepTracker` are created upfront so
the dashboard shows all goals from the moment the run starts.

Construct with `(config, ctx)`. `config` is a dict deep-merged into
:data:`~hackagent.attacks.techniques.advprefix.config.DEFAULT_PREFIX_GENERATION_CONFIG`.
There is no `advprefix_params` block and no
:class:`~hackagent.attacks.techniques.config.ConfigBase` subclass;
knobs stay at the top level of that dict. `ctx` is a
:class:`~hackagent.attacks.ports.RunContext`, passed positionally or
as `ctx=`. Tests build it with `make_ctx()`
(`tests.fakes.context`).

The legacy constructor `(config_dict, client, agent_router)` is
obsolete for new code. `hackagent.orchestrator.runner` constructs
`(config, ctx)`. Selection on that path uses `ctx.judge.evaluate`.

**Attributes**:

- `config` - Merged AdvPrefix configuration dictionary.
- `ctx` - RunContext on the new seam, otherwise None.
- `logger` - Hierarchical logger at `hackagent.attacks.advprefix`.

#### \_\_init\_\_

```python
def __init__(config: Optional[Dict[str, Any]] = None,
             ctx_or_client: Any = None,
             agent_router: Optional[LLMRouter] = None,
             *,
             ctx: Optional[RunContext] = None,
             client: Optional[Store] = None)
```

Initialize the AdvPrefix attack pipeline.

**Arguments**:

- `config` - Optional dictionary of parameter overrides merged into
  :data:`~hackagent.attacks.techniques.advprefix.config.DEFAULT_PREFIX_GENERATION_CONFIG`
  using a deep-merge strategy (nested dicts are merged;
  internal keys starting with `_` are passed by reference).
- `ctx` - :class:`~hackagent.attacks.ports.RunContext`. Positional
  or `ctx=`. Tests use `make_ctx()`. Selection then calls
  `ctx.judge.evaluate`.
- `client` - Obsolete. Store instance on the orchestrator path.
- `agent_router` - Obsolete. Target router on the orchestrator path.
  

**Raises**:

- `ValueError` - On the legacy path, if `client` or
  `agent_router` is `None`.

#### run

```python
def run(goals: Optional[List[str]] = None, **kwargs) -> List[AttackResult]
```

Executes the full prefix generation pipeline.

Goal Results are created upfront (before any pipeline step) so the
dashboard shows all goals from the moment the run starts.  Goals that
are filtered out during Generation are marked with an explanatory note
during finalization rather than simply having no record.

**Arguments**:

- `goals` - A list of goal strings to generate prefixes for.
  

**Returns**:

  List of dictionaries containing the final selected prefixes,
  or empty list if no prefixes were generated.

