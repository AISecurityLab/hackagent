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
prompt based on the *target* model&#x27;s responses and a judge score:

1. The attacker generates an initial or refined jailbreak prompt.
2. The prompt is sent to the target model.
3. A judge rates the response on a 1–10 jailbreak success scale.
4. The score and response are fed back to the attacker as context
for the next refinement.
5. Steps 1–4 repeat for `n_iterations` rounds or until early stop.

Multiple independent `n_streams` are run in parallel (one per goal);
each stream maintains its own conversation history with the attacker.

The attack requires three separate model roles:

* **Attacker** (`config[&quot;attacker&quot;]`) — an LLM that proposes prompt
improvements based on feedback.
* **Target** — the victim model reached via `agent_router`.
* **Judge** — same router as attacker (called with the judge prompt
from :data:`~hackagent.attacks.techniques.pair.config.JUDGE_SYSTEM_PROMPT`).

**Attributes**:

- `config` - Merged PAIR configuration dictionary.
- ``0 - Authenticated HackAgent API client.
- ``1 - Router for the victim model.
- ``2 - Router for the attacker/judge LLM.
- `3 - Loaded :class:`4
  instance for the configured `objective` key.
- `7 - Hierarchical logger at `hackagent.attacks.pair``.

#### \_\_init\_\_

```python
def __init__(config: Optional[Dict[str, Any]] = None,
             client: Optional[AuthenticatedClient] = None,
             agent_router: Optional[AgentRouter] = None)
```

Initialize PAIR attack.

**Arguments**:

- `config` - Optional configuration overrides merged into
  :data:`~hackagent.attacks.techniques.pair.config.DEFAULT_PAIR_CONFIG`.
- `client` - Authenticated HackAgent API client.
- `agent_router` - Router for the victim model.
  

**Raises**:

- `ValueError` - If `client` or `agent_router` is `None`, if
  the attacker router cannot be initialised, or if the
  configured `objective` key is not in
  :data:`~hackagent.attacks.techniques.pair.config.DEFAULT_PAIR_CONFIG`3.

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

