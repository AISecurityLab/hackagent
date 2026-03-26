---
sidebar_label: attack
title: hackagent.attacks.techniques.tap.attack
---

TAP (Tree of Attacks with Pruning) attack implementation.

Implements the TAP algorithm from:
    Mehrotra et al., &quot;Tree of Attacks with Pruning: Efficient
    Adversarial Prompting of Large Language Models&quot; (2023)
    https://arxiv.org/abs/2312.02119

Algorithm overview
------------------
TAP performs a bounded tree search where each node represents an
attacker-generated prompt candidate:

1. **Branching** — an attacker LLM generates `branching_factor`
   refinements of the current prompt in parallel `n_streams` streams.
2. **On-topic pruning** — a judge (or the main judge) discards branches
   whose prompts have drifted off-topic (`min_on_topic_score` threshold).
3. **Target query** — surviving prompts are sent to the victim model.
4. **Score pruning** — only the top-`width` branches by jailbreak score
   are kept for the next depth level.
5. **Termination** — search stops when `depth` levels are exhausted or
   a branch exceeds `success_score_threshold`.

Key parameters (`tap_params` in config)
-----------------------------------------
depth
    Maximum tree depth (number of refinement rounds per stream).
width
    Maximum branches kept after scoring at each depth level.
branching_factor
    Prompt refinements generated per active branch at each step.
n_streams
    Number of independent root-to-leaf searches run in parallel.
keep_last_n
    Conversation history window per stream (controls attacker context size).
early_stop_on_success
    Stop all streams as soon as one branch crosses the success threshold.
min_on_topic_score
    Minimum on-topic score (0 or 1) to retain a branch after on-topic pruning.
success_score_threshold
    Judge score that signals a successful jailbreak (default 1 for binary judges).

## TAPAttack Objects

```python
class TAPAttack(BaseAttack)
```

TAP (Tree of Attacks with Pruning) attack.

Orchestrates the TAP tree search by delegating to
:mod:`~hackagent.attacks.techniques.tap.generation` (attacker loop
and target queries) and
:mod:`~hackagent.attacks.techniques.tap.evaluation` (judge scoring).

The attack expects three collaborating models configured via
`config`:

* **Attacker** (`config[&quot;attacker&quot;]`) — LLM that proposes prompt
refinements from conversation history.
* **Target** — the victim model reached via `agent_router`.
* **Judge** (`config[&quot;judge&quot;]`) — LLM that rates jailbreak success
0–10 (or 0/1 for binary judges such as HarmBench).
* **On-topic judge** (`config[&quot;on_topic_judge&quot;]`, optional) —
separate evaluator that checks whether a prompt stays on-topic.
When `None`, the configured judge is reused with the on-topic
evaluation type.

The :meth:`~hackagent.attacks.techniques.tap.evaluation`4 method manages the full pipeline via
:class:`~hackagent.attacks.techniques.tap.evaluation`5:
a coordinator handles per-goal :class:`~hackagent.attacks.techniques.tap.evaluation`6
lifecycle and pipeline-level :class:`~hackagent.attacks.techniques.tap.evaluation`7
checkpointing.

**Attributes**:

- `~hackagent.attacks.techniques.tap.evaluation`8 - Merged TAP configuration dictionary.
- `~hackagent.attacks.techniques.tap.evaluation`9 - Authenticated HackAgent API client.
- ``0 - Router for the victim model.
- `1 - Hierarchical logger at `hackagent.attacks.tap``.

#### \_\_init\_\_

```python
def __init__(config: Optional[Dict[str, Any]] = None,
             client: Optional[AuthenticatedClient] = None,
             agent_router: Optional[AgentRouter] = None)
```

Initialize TAP with configuration and routers.

**Arguments**:

- `config` - Optional config overrides merged into
  :data:`~hackagent.attacks.techniques.tap.config.DEFAULT_TAP_CONFIG`.
  Keys from `config` win over defaults; nested dicts are
  deep-merged via :func:`_recursive_update`.
- `client` - Authenticated API client.
- `agent_router` - Router for the victim model.
  

**Raises**:

- `ValueError` - If `client` or `agent_router` is `None`.

#### run

```python
@with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
def run(goals: List[str]) -> List[Dict[str, Any]]
```

Run TAP end-to-end with unified tracking and pipeline steps.

**Arguments**:

- `goals` - List of goal strings to attack.
  

**Returns**:

  List of per-goal result dicts produced by the pipeline.

