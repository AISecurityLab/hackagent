---
sidebar_label: progress
title: hackagent.attacks._lib.progress
---

Shared progress bar utilities for attack modules.

This module provides standardized progress bar functionality that can be used
across all attack techniques for consistent visual feedback during execution.

## NullProgress Objects

```python
class NullProgress()
```

No-op progress bar with the same methods as a Rich `Progress`.

#### create\_progress\_bar

```python
@contextmanager
def create_progress_bar(description: str, total: int)
```

Create a standardized progress bar for attack pipeline steps.

This context manager provides a consistent progress bar configuration
across all attack types, ensuring uniform progress reporting UX.

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

  &gt;&gt;&gt; with create_progress_bar(&quot;[cyan]Processing prompts...&quot;, len(data)) as (progress, task):
  ...     for item in data:
  ...         # Process item
  ...         progress.update(task, advance=1)
  

**Notes**:

  The progress bar automatically starts and stops when entering/exiting
  the context manager.

#### report\_progress

```python
def report_progress(events: Any, fraction: float, message: str = "") -> None
```

Report progress through an :class:`~hackagent.attacks.ports.Events` sink.

Techniques should prefer this over Rich bars when a `RunContext` is
available. *events* may be `None` (no-op) for legacy construction.

