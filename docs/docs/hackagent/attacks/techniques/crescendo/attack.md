---
sidebar_label: attack
title: hackagent.attacks.techniques.crescendo.attack
---

Crescendo attack implementation.

Implements the Crescendo multi-turn jailbreak attack: an attacker LLM
gradually escalates a single, persistent conversation with the target model,
using the target&#x27;s own prior answers as context to make each new question
feel like a natural continuation, until the target eventually produces the
harmful content described in the goal.

Reference:
    Russinovich, Salem, Eldan, &quot;Great, Now Write an Article About That: The
    Crescendo Multi-Turn LLM Jailbreak Attack&quot; (2024)
    https://arxiv.org/abs/2404.01833
    https://crescendo-the-multiturn-jailbreak.github.io

Unlike single-turn attacks (PAIR, TAP, ...), Crescendo keeps one growing
`target_messages` conversation across the whole goal: every accepted turn
is appended to it and re-sent in full on the next request, so the target
sees genuine multi-turn context. This is HackAgent&#x27;s first attack to rely on
that behaviour; no router changes were required because `AgentRouter`
already forwards an arbitrary `messages` history verbatim to the target
adapter on every call.

Result Tracking:
    Uses TrackingCoordinator to manage both pipeline-level StepTracker
    and per-goal Tracker, matching the other iterative attacks (PAIR/TAP).

## CrescendoAttack Objects

```python
class CrescendoAttack(BaseAttack)
```

Crescendo multi-turn jailbreak attack.

Crescendo maintains a single, persistent conversation with the target
model. An attacker LLM proposes the next question given the FINAL GOAL
and the conversation so far, using the target&#x27;s own previous answer as
context so each escalation feels natural:

1. The attacker proposes the next question (benign at first, gradually
narrowing toward the goal).
2. The question is appended to `target_messages` and the *full*
conversation is sent to the target.
3. A judge rates the response (1-10) and flags whether it is a refusal.
4. If refused, the turn is *backtracked*: the question/answer pair is
dropped from `target_messages` and the attacker is asked to
rephrase the same step, up to `max_backtracks` times across the
conversation.
5. If accepted, the turn is kept and the loop advances, stopping early
once `jailbreak_threshold` is reached or `max_turns` is exhausted.

The attack requires two separate model roles:

* **Attacker** (`config[&quot;attacker&quot;]`) — an LLM that proposes the next
escalating question based on the conversation so far.
* **Target** — the victim model reached via `agent_router`, addressed
with the full, growing conversation history on every turn.
* **Judge** (`config[&quot;judge&quot;]`) — rates each target turn and detects
refusals, driving both scoring and the backtrack mechanism.

**Attributes**:

- `config` - Merged Crescendo configuration dictionary.
- `client` - Authenticated HackAgent API client.
- `agent_router` - Router for the victim model.
- `attacker_router` - Router for the attacker LLM.
- `judge_router` - Router for the judge LLM.
- `objective` - Loaded :class:`~hackagent.attacks.objectives.base.ObjectiveConfig`
  instance for the configured `objective` key.
- `logger` - Hierarchical logger at `hackagent.attacks.crescendo`.

#### \_\_init\_\_

```python
def __init__(config: Optional[Dict[str, Any]] = None,
             client: Optional[AuthenticatedClient] = None,
             agent_router: Optional[AgentRouter] = None)
```

Initialize Crescendo attack.

**Arguments**:

- `config` - Optional configuration overrides merged into
  :data:`~hackagent.attacks.techniques.crescendo.config.DEFAULT_CRESCENDO_CONFIG`.
- `client` - Authenticated HackAgent API client.
- `agent_router` - Router for the victim model.
  

**Raises**:

- `ValueError` - If `client` or `agent_router` is `None`, if the
  attacker router cannot be initialised, or if the configured
  `objective` key is not in
  :data:`~hackagent.attacks.objectives.OBJECTIVES`.

#### run

```python
@with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
def run(goals: Optional[List[str]] = None, **kwargs) -> List[AttackResult]
```

Execute Crescendo attack on goals.

**Arguments**:

- `goals` - List of harmful goals to test
  

**Returns**:

  List of attack results with scores

