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

Implements the PAIR algorithm from:
Chao et al., &quot;Jailbreaking Black Box Large Language Models
in Twenty Queries&quot; (2023)
https://arxiv.org/abs/2310.08419

PAIR uses an *attacker* LLM to iteratively refine an adversarial
prompt based on the *target* model&#x27;s responses and a scorer score:

1. The attacker generates an initial or refined jailbreak prompt.
2. The prompt is sent to the target model.
3. A scorer rates the response on a 1–10 jailbreak success scale.
4. The score and response are fed back to the attacker as context
for the next refinement.
5. Steps 1–4 repeat for `n_iterations` rounds or until early stop.

Multiple independent `n_streams` are run in parallel (one per goal);
each stream maintains its own conversation history with the attacker.

The attack requires three separate model roles:

* **Attacker** (`config[&quot;attacker&quot;]`) — an LLM that proposes prompt
improvements based on feedback.
* **Target** — the victim model reached via `agent_router`.
* **Scorer** (`config[&quot;scorer&quot;]`) — dedicated scorer model using
the AutoDAN-Turbo scorer+wrapper protocol.

**Attributes**:

- `config` - Merged PAIR configuration dictionary.
- `client` - Authenticated HackAgent API client.
- `agent_router` - Router for the victim model.
- `attacker_router` - Router for the attacker LLM.
- `scorer_router` - Router for the scorer LLM.
- `objective` - Loaded :class:`~hackagent.attacks.objectives.base.ObjectiveConfig`
  instance for the configured `objective` key.
- `logger` - Hierarchical logger at `hackagent.attacks.pair`.

#### \_\_init\_\_

```python
def __init__(config: Optional[Dict[str, Any]] = None,
             ctx_or_client: Any = None,
             agent_router: Optional[LLMRouter] = None,
             *,
             ctx: Optional[RunContext] = None,
             client: Optional[Store] = None)
```

Initialize PAIR with `(config, ctx)` or legacy args.

On the new seam the attacker role comes from `ctx.models` and
refinement scores come from `ctx.judge` (`verdict_from_judge`).
This class does not read `_suppress_run_status_updates`.
`PairConfig` still subclasses
:class:`~hackagent.attacks.techniques.config.ConfigBase`.
The legacy constructor is obsolete for new code.

#### run

```python
def run(goals: Optional[List[str]] = None, **kwargs) -> List[AttackResult]
```

Execute PAIR attack on goals.

Uses TrackingCoordinator to manage both pipeline-level and
per-goal result tracking through a single unified interface.

**Arguments**:

- `goals` - List of harmful goals to test
  

**Returns**:

  List of attack results with scores

