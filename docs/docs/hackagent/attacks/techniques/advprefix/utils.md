---
sidebar_label: utils
title: hackagent.attacks.techniques.advprefix.utils
---

Utility functions for AdvPrefix attacks.

This module provides common utility functions and helper methods used across
the AdvPrefix attack pipeline. All execution data is tracked via the API.

The module provides:
- Progress bar context managers for visual feedback
- LLM completion utilities for model interactions
- Processor step execution with standardized error handling
- String processing and text manipulation functions
- Common mathematical and statistical operations

These utilities promote code reuse and maintain consistency across the
different stages of the AdvPrefix attack pipeline.

#### create\_progress\_bar

```python
@contextmanager
def create_progress_bar(description: str, total: int)
```

Create a standardized progress bar for AdvPrefix pipeline steps.

This context manager provides a consistent progress bar configuration
across all pipeline stages, eliminating code duplication and ensuring
uniform progress reporting UX throughout the attack execution.

The progress bar includes:
- Spinner animation for visual feedback
- Task description with formatting support
- Visual progress bar
- Completion counter (M of N complete)
- Percentage complete
- Estimated time remaining

**Arguments**:

- `description` - Human-readable description of the task being tracked.
  Supports Rich markup formatting (e.g., &quot;[cyan]Processing...[/cyan]&quot;).
- `total` - Total number of items/iterations to process for completion tracking.
  

**Yields**:

  Tuple of (progress_bar, task_id):
  - progress_bar: Progress instance for manual control if needed
  - task_id: Task identifier for progress updates via progress_bar.update(task_id)
  

**Example**:

  &gt;&gt;&gt; with create_progress_bar(&quot;[cyan]Processing prefixes...&quot;, len(data)) as (progress, task):
  ...     for item in data:
  ...         # Process item
  ...         progress.update(task, advance=1)
  

**Notes**:

  The progress bar automatically starts and stops when entering/exiting
  the context manager. All pipeline steps should use this utility for
  consistent progress reporting.

#### handle\_empty\_input

```python
def handle_empty_input(step_name: str, empty_result: Any = None)
```

Decorator to handle empty input data (list/dict).

**Arguments**:

- `step_name` - Step name for logging
- `empty_result` - What to return if input is empty (default: empty list)
  

**Example**:

  &gt;&gt;&gt; @handle_empty_input(&quot;Generate Prefixes&quot;, empty_result=[])
  ... def execute(goals, config, logger, client):
  ...     # goals will never be empty here
  ...     return results

#### require\_agent\_router

```python
def require_agent_router(step_name: str, agent_type: Optional[str] = None)
```

Decorator to validate agent_router parameter exists and is valid.

**Arguments**:

- `step_name` - Step name for error messages
- `agent_type` - Optional required agent type (e.g., &quot;GOOGLE_ADK&quot;)
  

**Example**:

  &gt;&gt;&gt; @require_agent_router(&quot;Compute CE&quot;, agent_type=&quot;GOOGLE_ADK&quot;)
  ... def execute(client, agent_router, input_df, config, logger):
  ...     # agent_router is guaranteed to be valid here
  ...     pass

#### log\_errors

```python
def log_errors(step_name: str)
```

Decorator to add consistent error logging.

**Arguments**:

- `step_name` - Step name for error messages
  

**Example**:

  &gt;&gt;&gt; @log_errors(&quot;Generate Prefixes&quot;)
  ... def execute(goals, config, logger, client):
  ...     # Any exception will be logged with step context
  ...     return results

#### validate\_config

```python
def validate_config(required_keys: List[str])
```

Decorator to validate configuration has required keys.

**Arguments**:

- `required_keys` - List of required configuration keys
  

**Example**:

  &gt;&gt;&gt; @validate_config([&quot;model_id&quot;, &quot;temperature&quot;, &quot;max_tokens&quot;])
  ... def execute(config, logger):
  ...     # config is guaranteed to have required keys
  ...     pass

