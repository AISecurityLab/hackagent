# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Shared progress bar utilities for attack modules.

This module provides standardized progress bar functionality that can be used
across all attack techniques for consistent visual feedback during execution.
"""

import os
from contextlib import contextmanager

# Import Rich progress bar components
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)


class NullProgress:
    """
    Null progress bar implementation for TUI mode.

    When running in TUI mode (NO_COLOR=1), progress bars are disabled
    to avoid conflicts with the TUI display. This class provides a
    no-op implementation that matches the Progress API.
    """

    def add_task(self, *args, **kwargs):
        return 0

    def update(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@contextmanager
def create_progress_bar(description: str, total: int):
    """
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

    Args:
        description: Human-readable description of the task being tracked.
            Supports Rich markup formatting (e.g., "[cyan]Processing...[/cyan]").
        total: Total number of items/iterations to process for completion tracking.

    Yields:
        Tuple of (progress_bar, task_id):
        - progress_bar: Progress instance for manual control if needed
        - task_id: Task identifier for progress updates via progress_bar.update(task_id)

    Example:
        >>> with create_progress_bar("[cyan]Processing prompts...", len(data)) as (progress, task):
        ...     for item in data:
        ...         # Process item
        ...         progress.update(task, advance=1)

    Note:
        The progress bar automatically starts and stops when entering/exiting
        the context manager. In TUI mode (NO_COLOR=1), a null progress bar
        is used to avoid display conflicts.
    """
    # Check if running in TUI mode (NO_COLOR env var is set by TUI)
    in_tui_mode = os.environ.get("NO_COLOR") == "1"

    if in_tui_mode:
        # In TUI mode: use a null progress bar that does nothing
        progress_bar = NullProgress()
        task = 0
        yield progress_bar, task
    else:
        # Normal mode: use Rich progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.1f}%"),
            TimeRemainingColumn(),
        ) as progress_bar:
            task = progress_bar.add_task(description, total=total)
            yield progress_bar, task
