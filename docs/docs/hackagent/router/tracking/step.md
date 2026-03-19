---
sidebar_label: step
title: hackagent.router.tracking.step
---

Step-level tracking functionality.

This module provides the StepTracker class which handles the lifecycle
of pipeline step tracking including trace creation, status updates, and
error handling. It integrates with the HackAgent backend API to maintain
synchronized state.

StepTracker is designed for tracking high-level pipeline steps (e.g.,
&quot;Generation&quot;, &quot;Evaluation&quot;) rather than individual datapoints. For per-goal
or per-datapoint tracking, use the Tracker class from tracker.py instead.

## StepTracker Objects

```python
class StepTracker()
```

Tracks pipeline step execution and synchronizes with backend API.

This class manages the complete lifecycle of step-level tracking:
- Creating trace records for each pipeline step
- Handling exceptions and updating error states
- Managing sequence counters for ordered operations
- Updating run and result statuses

Use StepTracker for high-level pipeline steps (e.g., &quot;Generation Step&quot;,
&quot;Evaluation Step&quot;). For per-goal/datapoint tracking with multiple traces
per result, use the Tracker class instead.

The tracker is designed to fail gracefully - if tracking is disabled
or API calls fail, the underlying operations continue unaffected.

**Attributes**:

- `context` - TrackingContext containing tracking configuration
- `logger` - Logger instance for tracking operations
  

**Example**:

  &gt;&gt;&gt; context = TrackingContext(client=client, run_id=&quot;123&quot;, parent_result_id=&quot;456&quot;)
  &gt;&gt;&gt; tracker = StepTracker(context)
  &gt;&gt;&gt;
  &gt;&gt;&gt; with tracker.track_step(&quot;Process Data&quot;, &quot;STEP1_PROCESS&quot;):
  ...     result = process_data()
  &gt;&gt;&gt;
  &gt;&gt;&gt; tracker.update_run_status(StatusEnum.COMPLETED)

#### \_\_init\_\_

```python
def __init__(context: TrackingContext)
```

Initialize the step tracker.

**Arguments**:

- `context` - TrackingContext instance with tracking configuration

#### track\_step

```python
@contextmanager
def track_step(step_name: str,
               step_type: str,
               input_data: Optional[Dict[str, Any]] = None,
               config: Optional[Dict[str, Any]] = None)
```

Context manager for tracking a single pipeline step.

This context manager handles the complete lifecycle of step tracking:
1. Creates a trace record at step start
2. Yields control to the caller
3. Handles exceptions and updates error states
4. Ensures proper cleanup

**Arguments**:

- `step_name` - Human-readable step name
- `step_type` - Step type identifier (e.g., &quot;STEP1_GENERATE&quot;)
- `input_data` - Optional input data sample for tracking
- `config` - Optional configuration snapshot for this step
  

**Yields**:

- `trace_id` - ID of the created trace record (or None if tracking disabled)
  

**Example**:

  &gt;&gt;&gt; with tracker.track_step(&quot;Generate Prefixes&quot;, &quot;STEP1_GENERATE&quot;):
  ...     prefixes = generate_prefixes(goals)
  ...     # Step automatically tracked
  

**Raises**:

  Re-raises any exception from the tracked code block after
  recording the error state.

#### update\_run\_status

```python
def update_run_status(status: StatusEnum) -> bool
```

Update the run status on the backend.

**Arguments**:

- `status` - New status to set
  

**Returns**:

  True if update was successful, False otherwise

#### update\_result\_status

```python
def update_result_status(
        evaluation_status: EvaluationStatusEnum,
        evaluation_notes: Optional[str] = None,
        agent_specific_data: Optional[Dict[str, Any]] = None) -> bool
```

Update the result evaluation status.

**Arguments**:

- `evaluation_status` - Evaluation status to set
- `evaluation_notes` - Optional notes about the evaluation
- `agent_specific_data` - Optional agent-specific result data
  

**Returns**:

  True if update was successful, False otherwise

#### add\_step\_metadata

```python
def add_step_metadata(key: str, value: Any) -> None
```

Add metadata that will be included in the next trace.

This allows steps to record additional information like:
- Item counts (e.g., &quot;prefixes_generated&quot;: 150)
- Processing stats (e.g., &quot;success_rate&quot;: 0.85)
- Warnings (e.g., &quot;empty_results&quot;: True)

**Arguments**:

- `key` - Metadata key
- `value` - Metadata value (must be JSON-serializable)
  

**Example**:

  &gt;&gt;&gt; tracker.add_step_metadata(&quot;items_processed&quot;, 100)
  &gt;&gt;&gt; tracker.add_step_metadata(&quot;warning&quot;, &quot;Some items filtered&quot;)

#### record\_progress

```python
def record_progress(message: str, **metrics) -> None
```

Record progress information during step execution.

This is useful for long-running operations to track intermediate
progress without cluttering logs. Information is added to context
metadata and will be included in the next trace update.

**Arguments**:

- `message` - Progress message
- `**metrics` - Additional metrics as keyword arguments
  

**Example**:

  &gt;&gt;&gt; tracker.record_progress(&quot;Processing batch 1/10&quot;, items=50, errors=0)

