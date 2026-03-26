---
sidebar_label: coordinator
title: hackagent.router.tracking.coordinator
---

Tracking coordinator for attack techniques.

This module provides the TrackingCoordinator class, which unifies the two
parallel tracking systems (StepTracker for pipeline steps, Tracker for
per-goal results) into a single, coherent API.

Design Goals:
    - Single entry point for all tracking operations
    - Owns the lifecycle of both StepTracker and Tracker
    - Provides crash-safe finalization (all goals finalized on error)
    - Enriches pipeline data with result_ids at well-defined points
    - Eliminates config-dict smuggling of tracking context

Architecture:
    BaseAttack.run()
      └─ TrackingCoordinator
           ├─ step_tracker: StepTracker  (pipeline step tracking)
           ├─ goal_tracker: Tracker      (per-goal result tracking)
           └─ finalize_on_error()        (crash safety)

Usage:
    coordinator = TrackingCoordinator.create(
        client=client,
        run_id=run_id,
        logger=logger,
        attack_type=&quot;advprefix&quot;,
    )
    coordinator.initialize_goals(goals, initial_metadata=\{...\})

    # Pass coordinator.goal_tracker to sub-modules explicitly
    # (not via config dict)

    # After pipeline completes:
    coordinator.finalize_all_goals(results, scorer=my_scorer)

    # On error:
    coordinator.finalize_on_error(&quot;Pipeline failed&quot;)

## TrackingCoordinator Objects

```python
class TrackingCoordinator()
```

Unified tracking coordinator for attack techniques.

Wraps both StepTracker (pipeline-level) and Tracker (goal-level) into
a single interface. Provides:

- Goal lifecycle management (create, trace, finalize)
- Pipeline step tracking via StepTracker
- Crash-safe finalization (all goals finalized on error)
- Data enrichment (inject result_ids into pipeline data)
- Summary statistics

**Attributes**:

- `step_tracker` - StepTracker for pipeline step tracking
- `goal_tracker` - Tracker for per-goal result tracking
- `is_enabled` - Whether tracking is active

#### \_\_init\_\_

```python
def __init__(step_tracker: StepTracker,
             goal_tracker: Optional[Tracker],
             logger: Optional[logging.Logger] = None)
```

Initialize coordinator with pre-built trackers.

Prefer using TrackingCoordinator.create() factory method instead.

**Arguments**:

- `step_tracker` - StepTracker for pipeline steps
- `goal_tracker` - Optional Tracker for per-goal tracking
- `logger` - Logger instance

#### create

```python
@classmethod
def create(
    cls,
    backend: Any,
    run_id: Optional[str],
    logger: Optional[logging.Logger] = None,
    attack_type: str = "unknown",
    goals: Optional[List[str]] = None,
    initial_metadata: Optional[Dict[str,
                                    Any]] = None) -> "TrackingCoordinator"
```

Factory method to create a fully-initialized coordinator.

**Arguments**:

- `backend` - StorageBackend (RemoteBackend or LocalBackend), or None to disable.
- `run_id` - Server-side run record ID (or None to disable)
- `logger` - Logger instance
- `attack_type` - Attack identifier (e.g., &quot;advprefix&quot;, &quot;pair&quot;)
- `goals` - Optional list of goals to initialize upfront
- `initial_metadata` - Optional metadata for goal results
  

**Returns**:

  Initialized TrackingCoordinator

#### create\_disabled

```python
@classmethod
def create_disabled(cls,
                    logger: Optional[logging.Logger] = None
                    ) -> "TrackingCoordinator"
```

Create a coordinator with tracking disabled.

Useful for testing or when no API client is available.

**Returns**:

  TrackingCoordinator with noop tracking

#### is\_enabled

```python
@property
def is_enabled() -> bool
```

Whether tracking is active (has client + run_id).

#### has\_goal\_tracking

```python
@property
def has_goal_tracking() -> bool
```

Whether per-goal tracking is available.

#### initialize\_goals

```python
def initialize_goals(
        goals: List[str],
        initial_metadata: Optional[Dict[str, Any]] = None) -> None
```

Create Result records for all goals upfront.

This should be called once at the start of the attack, before
any pipeline steps execute.

**Arguments**:

- `goals` - List of goal strings
- `initial_metadata` - Optional metadata to attach to each goal result

#### initialize\_goals\_from\_pipeline\_data

```python
def initialize_goals_from_pipeline_data(
        pipeline_data: List[Dict[str, Any]],
        initial_metadata: Optional[Dict[str, Any]] = None) -> None
```

Create Result records only for goals that survived the Generation step.

Extracts unique goals from pipeline output data and initializes
tracking only for those goals. Goals that were filtered out during
Generation get no Result record.

**Arguments**:

- `pipeline_data` - Output from the Generation step (list of dicts with &quot;goal&quot; key)
- `initial_metadata` - Optional metadata to attach to each goal result

#### get\_goal\_context

```python
def get_goal_context(goal_index: int) -> Optional[Context]
```

Get tracking context for a specific goal by index.

#### get\_goal\_context\_by\_goal

```python
def get_goal_context_by_goal(goal: str) -> Optional[Context]
```

Get tracking context for a specific goal by text.

#### enrich\_with\_result\_ids

```python
def enrich_with_result_ids(data: List[Dict]) -> List[Dict]
```

Inject result_id from goal contexts into pipeline data rows.

This is the single, well-defined point where result_ids flow from
the Tracker into the pipeline data. Call this after the completions
step and before evaluation.

**Arguments**:

- `data` - List of dicts, each with a &quot;goal&quot; key
  

**Returns**:

  Same list with &quot;result_id&quot; added where available

#### finalize\_all\_goals

```python
def finalize_all_goals(results: Optional[List[Dict]],
                       scorer: Optional[Callable[[List[Dict]], bool]] = None,
                       success_threshold: float = 0.5,
                       include_evaluation_trace: bool = True) -> None
```

Finalize all goal results based on pipeline output.

Uses a scorer function to determine success per goal. If no scorer
is provided, uses default logic based on evaluation columns.

**Arguments**:

- `results` - Pipeline output (list of prefix/result dicts)
- `scorer` - Optional function (goal_results) -&gt; bool for success
- `success_threshold` - Default threshold for eval score success
- `include_evaluation_trace` - Whether to emit a generic &quot;Evaluation&quot;
  trace for each goal during finalization.

#### finalize\_on\_error

```python
def finalize_on_error(error_message: str = "Pipeline failed") -> None
```

Crash-safe finalization: mark all unfinalized goals as failed.

Call this in an except/finally block to ensure no goals remain
in NOT_EVALUATED state.

**Arguments**:

- `error_message` - Description of the failure

#### finalize\_pipeline

```python
def finalize_pipeline(results: Any,
                      success_check: Optional[Callable] = None) -> None
```

Finalize pipeline-level tracking (StepTracker).

Updates the run status to COMPLETED.  Per-goal evaluation statuses
are already set by `finalize_all_goals`.

**Arguments**:

- `results` - Pipeline output (used only if success_check is provided)
- `success_check` - Optional callable to determine overall success

#### get\_summary

```python
def get_summary() -> Dict[str, Any]
```

Get combined summary from both tracking systems.

#### log\_summary

```python
def log_summary() -> None
```

Log a human-readable summary.

