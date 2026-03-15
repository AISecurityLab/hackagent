---
sidebar_label: tracker
title: hackagent.router.tracking.tracker
---

Goal-based result tracking for attack techniques.

This module provides the main Tracker class which creates one Result per
goal/datapoint and accumulates traces for each interaction during the attack.
This addresses the issue of having too many Results (one per LLM call) with
only 1-2 traces each.

Architecture:
    Attack → Tracker → Result per goal → Multiple Traces per Result

Each attack creates one Result per goal/datapoint via Tracker,
then accumulates traces for each interaction during the attack.

For step-level tracking (pipeline steps like &quot;Generation&quot;, &quot;Evaluation&quot;),
use the StepTracker class from step.py instead.

## Context Objects

```python
@dataclass
class Context()
```

Context for tracking a single goal&#x27;s attack execution.

#### increment\_sequence

```python
def increment_sequence() -> int
```

Atomically increment and return the next sequence number.

#### elapsed\_s

```python
@property
def elapsed_s() -> float
```

Wall-clock seconds since context creation (or until finalized).

## Tracker Objects

```python
class Tracker()
```

Tracks attack execution on a per-goal basis.

Creates one Result per goal, with multiple Traces capturing:
- Attack attempts (prompts sent, responses received)
- Intermediate steps (judge evaluations, refinements)
- Final evaluation status

This provides better organization of results where each Result represents
a complete attack attempt on a single goal/datapoint.

**Attributes**:

- `client` - Authenticated client for API calls
- `run_id` - Server-side run record ID
- `logger` - Logger instance
  

**Example**:

  &gt;&gt;&gt; tracker = Tracker(client=client, run_id=run_id)
  &gt;&gt;&gt;
  &gt;&gt;&gt; for goal in goals:
  ...     # Create result for this goal
  ...     goal_ctx = tracker.create_goal_result(goal, goal_index=i)
  ...
  ...     # Add traces for each attack attempt
  ...     for iteration in range(n_iterations):
  ...         response = query_target(prompt)
  ...         tracker.add_interaction_trace(
  ...             goal_ctx,
  ...             request=&#123;&quot;prompt&quot;: prompt&#125;,
  ...             response=&#123;&quot;content&quot;: response&#125;,
  ...             step_name=&quot;Attack Attempt&quot;
  ...         )
  ...
  ...     # Finalize with evaluation
  ...     tracker.finalize_goal(
  ...         goal_ctx,
  ...         success=is_success,
  ...         evaluation_notes=&quot;Attack succeeded with score 10/10&quot;
  ...     )

#### \_\_init\_\_

```python
def __init__(backend: StorageBackend,
             run_id: str,
             logger: Optional[logging.Logger] = None,
             attack_type: Optional[str] = None)
```

Initialize tracker.

**Arguments**:

- `client` - Authenticated client for API calls
- `run_id` - Server-side run record ID
- `logger` - Optional logger instance
- `attack_type` - Optional attack type identifier for metadata

#### is\_enabled

```python
@property
def is_enabled() -> bool
```

Check if tracking is enabled (has backend and run_id).

#### create\_goal\_result

```python
def create_goal_result(
        goal: str,
        goal_index: int,
        initial_metadata: Optional[Dict[str, Any]] = None) -> Context
```

Create a Result record for a goal and return its tracking context.

**Arguments**:

- `goal` - The goal/datapoint text
- `goal_index` - Index of this goal in the batch
- `initial_metadata` - Optional initial metadata to store
  

**Returns**:

  Context for tracking this goal&#x27;s attack execution

#### add\_interaction\_trace

```python
def add_interaction_trace(ctx: Context,
                          request: Dict[str, Any],
                          response: Any,
                          step_name: str = "Agent Interaction",
                          step_type: StepTypeEnum = StepTypeEnum.OTHER,
                          metadata: Optional[Dict[str, Any]] = None) -> None
```

Add a trace for an agent interaction (request/response pair).

**Arguments**:

- `ctx` - Context from create_goal_result
- `request` - Request data sent to the agent
- `response` - Response received from the agent
- `step_name` - Human-readable step name
- `step_type` - Type of step for categorization
- `metadata` - Optional additional metadata

#### add\_evaluation\_trace

```python
def add_evaluation_trace(ctx: Context,
                         evaluation_result: Any,
                         score: Optional[float] = None,
                         explanation: Optional[str] = None,
                         evaluator_name: Optional[str] = None,
                         metadata: Optional[Dict[str, Any]] = None) -> None
```

Add a trace for an evaluation step.

**Arguments**:

- `ctx` - Context from create_goal_result
- `evaluation_result` - Result from the evaluator
- `score` - Optional numeric score
- `explanation` - Optional explanation text
- `evaluator_name` - Name of the evaluator used
- `metadata` - Optional additional metadata

#### add\_custom\_trace

```python
def add_custom_trace(ctx: Context,
                     step_name: str,
                     content: Dict[str, Any],
                     step_type: StepTypeEnum = StepTypeEnum.OTHER) -> None
```

Add a custom trace with arbitrary content.

**Arguments**:

- `ctx` - Context from create_goal_result
- `step_name` - Human-readable step name
- `content` - Trace content dictionary
- `step_type` - Type of step for categorization

#### finalize\_goal

```python
def finalize_goal(ctx: Context,
                  success: bool,
                  evaluation_notes: Optional[str] = None,
                  final_metadata: Optional[Dict[str, Any]] = None) -> bool
```

Finalize a goal&#x27;s result with evaluation status.

**Arguments**:

- `ctx` - Context from create_goal_result
- `success` - Whether the attack was successful
- `evaluation_notes` - Optional evaluation notes
- `final_metadata` - Optional final metadata to merge
  

**Returns**:

  True if update was successful, False otherwise

#### get\_goal\_context

```python
def get_goal_context(goal_index: int) -> Optional[Context]
```

Get the Context for a specific goal index.

#### get\_goal\_context\_by\_goal

```python
def get_goal_context_by_goal(goal: str) -> Optional[Context]
```

Get the Context for a specific goal string.

Searches all contexts to find one matching the goal text.
Use this when you have the goal string but not the index.

**Arguments**:

- `goal` - The goal text to find
  

**Returns**:

  Context if found, None otherwise

#### get\_result\_id

```python
def get_result_id(goal_index: int) -> Optional[str]
```

Get the result ID for a specific goal index.

#### get\_all\_contexts

```python
def get_all_contexts() -> Dict[int, Context]
```

Get all goal contexts.

#### get\_summary

```python
def get_summary() -> Dict[str, Any]
```

Get summary statistics for all tracked goals.

#### track\_goal

```python
@contextmanager
def track_goal(goal: str,
               goal_index: int,
               initial_metadata: Optional[Dict[str, Any]] = None)
```

Context manager for tracking a single goal&#x27;s attack execution.

Creates result on entry, yields context for adding traces,
and auto-finalizes on exit (with failure status if exception occurs).

**Arguments**:

- `goal` - The goal/datapoint text
- `goal_index` - Index of this goal
- `initial_metadata` - Optional initial metadata
  

**Yields**:

  Context for adding traces during execution
  

**Example**:

  &gt;&gt;&gt; with tracker.track_goal(goal, i) as ctx:
  ...     response = attack(goal)
  ...     tracker.add_interaction_trace(ctx, request, response)
  ...     # Finalize manually or let context manager handle it

