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

1. **Generation** — uses an uncensored generator LLM to produce
candidate adversarial prefixes for each harmless meta-prompt.
Prefixes are filtered by cross-entropy (``max_ce``) and token
segment count before being passed downstream.
2. **Execution** — appends each surviving prefix to the target model
prompt and collects completions (``n_samples`` per prefix).
3. **Evaluation** — LLM judges (e.g. HarmBench) rate each completion;
the top-``n_prefixes_per_goal`` prefixes per goal are selected and
returned.

The class delegates stage logic to dedicated sub-modules:

* :mod:`~hackagent.attacks.techniques.advprefix.generate`
(:class:`PrefixGenerationPipeline`) for steps 1 and internal
filtering.
* :mod:`~hackagent.attacks.techniques.advprefix.completions` for
step 2.
* :mod:`~hackagent.attacks.techniques.advprefix.evaluation`
(:class:``0) for step 3.

Tracking is managed by
:class:``1; goal
:class:``2 instances and a pipeline
:class:``3 are created upfront so
the dashboard shows all goals from the moment the run starts.

**Attributes**:

- ``4 - Merged AdvPrefix configuration dictionary.
- ``5 - Authenticated HackAgent API client.
- ``6 - Router for the victim model.
- ``7 - Hierarchical logger at ``hackagent.attacks.advprefix``.

#### \_\_init\_\_

```python
def __init__(config: Optional[Dict[str, Any]] = None,
             client: Optional[AuthenticatedClient] = None,
             agent_router: Optional[AgentRouter] = None)
```

Initialize the AdvPrefix attack pipeline.

**Arguments**:

- `config` - Optional dictionary of parameter overrides merged into
  :data:`~hackagent.attacks.techniques.advprefix.config.DEFAULT_PREFIX_GENERATION_CONFIG`
  using a deep-merge strategy (nested dicts are merged;
  internal keys starting with ``_`` are passed by reference).
- `client` - Authenticated HackAgent API client.
- `agent_router` - Router for the victim model.
  

**Raises**:

- `ValueError` - If ``client`` or ``agent_router`` is ``None``.

#### run

```python
@with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
def run(goals: List[str]) -> List[Dict]
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

