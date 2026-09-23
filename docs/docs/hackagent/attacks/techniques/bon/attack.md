---
sidebar_label: attack
title: hackagent.attacks.techniques.bon.attack
---

Best-of-N (BoN) Jailbreaking attack implementation.

Stochastic black-box attack that generates N randomly augmented versions of a
harmful prompt — using word scrambling, random capitalization, and ASCII
perturbation — and picks the best candidate that elicits a harmful response
from the target model.

The attack runs in two pipeline stages:
1. **Generation** — multi-step search with K parallel candidates per step.
2. **Evaluation** — multi-judge scoring via BaseEvaluationStep.

Based on: https://arxiv.org/abs/2412.03556

Result Tracking:
    Uses TrackingCoordinator to manage both pipeline-level StepTracker
    and per-goal Tracker.  The coordinator handles goal lifecycle,
    crash-safe finalization, and data enrichment (result_id injection).

## BoNAttack Objects

```python
class BoNAttack(BaseAttack)
```

Best-of-N (BoN) Jailbreaking — stochastic text augmentation attack.

Implements the Best-of-N technique from:
    Hughes et al., &quot;Best-of-N Jailbreaking&quot; (2024)
    https://arxiv.org/abs/2412.03556

For each goal the attack runs ``n_steps`` sequential search steps.
Within each step, ``num_concurrent_k`` independently-seeded augmented
candidates are generated and sent to the target model in parallel.
The best candidate is selected by response length (as a proxy for
non-refusal), and a final multi-judge evaluation scores the result.

Pipeline:
    1. Generation — multi-step BoN search with text augmentations.
       On ``BaseAttack(config, ctx)``, candidates are scored with
       ``ctx.judge.score`` through
       :class:`~hackagent.attacks._lib.inline_judge.CtxJudgeAdapter`.
       ``InlineStepJudge`` remains the fallback when ``ctx`` is absent.

Construct with ``(config, ctx)``. Tests build ``ctx`` with
``make_ctx()`` (``tests.fakes.context``). The legacy constructor
``(config_dict, client, agent_router)`` is obsolete for new code.
:class:`~hackagent.attacks.techniques.bon.config.BoNConfig` still
subclasses :class:`~hackagent.attacks.techniques.config.ConfigBase`.

#### \_\_init\_\_

```python
def __init__(config: Optional[Dict[str, Any]] = None,
             ctx_or_client: Any = None,
             agent_router: Optional[LLMRouter] = None,
             *,
             ctx: Optional[RunContext] = None,
             client: Optional[Store] = None)
```

Initialise BoNAttack with configuration.

Prefer ``BoNAttack(config, ctx)``. ``ctx.judge.score`` replaces
``InlineStepJudge`` on that path. Legacy
``(config, client, agent_router)`` remains for the orchestrator
and is obsolete for new code.

#### run

```python
def run(goals: Optional[List[str]] = None, **kwargs) -> List[AttackResult]
```

Execute the full BoN attack pipeline.

The generation step performs the multi-step BoN search **and** inline
judge evaluation.  If a judge confirms a jailbreak at any step the
search terminates early.  A lightweight post-processing step then
syncs results to the server and logs ASR.

**Arguments**:

- `goals` - A list of goal strings to test.
  

**Returns**:

  List of result dictionaries, or empty list if no goals provided.

