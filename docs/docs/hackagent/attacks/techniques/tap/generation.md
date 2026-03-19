---
sidebar_label: generation
title: hackagent.attacks.techniques.tap.generation
---

TAP generation and execution module.

Runs the Tree of Attacks with Pruning (TAP) loop, including on-topic
filtering, target querying, and iterative judging.

## TapExecutor Objects

```python
class TapExecutor()
```

Run the TAP search loop for a set of goals.

This class encapsulates the TAP algorithm: expand candidate prompts,
prune off-topic branches, query the target model, judge responses,
and keep the best branches across depths.

#### \_\_init\_\_

```python
def __init__(config: Dict[str, Any], client: AuthenticatedClient,
             agent_router: AgentRouter, logger: logging.Logger)
```

Prepare routers and judge configuration used in the search.

**Arguments**:

- `config` - TAP configuration dict (contains attacker/judge settings).
- `client` - Authenticated API client for router calls.
- `agent_router` - Router for the victim model.
- `logger` - Logger for TAP diagnostics.

#### run\_single\_goal

```python
def run_single_goal(goal: str,
                    goal_index: int,
                    goal_tracker: Optional[Tracker] = None,
                    goal_ctx: Optional[Context] = None,
                    progress_bar=None,
                    task=None) -> Dict[str, Any]
```

Execute TAP for one goal.

Algorithm: expand a tree of attacker prompts, prune off-topic
branches, query the target, judge results, then keep the top
scoring branches for the next depth.

**Arguments**:

- `goal` - The attack objective string.
- `goal_index` - Index of the goal in the run list.
- `goal_tracker` - Optional per-goal tracker for interaction traces.
- `goal_ctx` - Optional tracking context for this goal.
- `progress_bar` - Optional progress bar instance.
- `task` - Optional progress bar task identifier.
  

**Returns**:

  Result dict with best prompt/response, score, and metadata.

#### execute

```python
def execute(goals: List[str], agent_router: AgentRouter,
            config: Dict[str, Any], logger: logging.Logger,
            client: AuthenticatedClient) -> List[Dict[str, Any]]
```

Pipeline entry point for TAP generation and search.

**Arguments**:

- `goals` - List of goal strings to attack.
- `agent_router` - Router for the victim model.
- `config` - TAP configuration dict.
- `logger` - Logger for progress and diagnostics.
- `client` - Authenticated API client for attacker router creation.
  

**Returns**:

  List of per-goal result dicts (best prompt/response and scores).

