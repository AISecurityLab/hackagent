# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Operation tracking and synchronization module.

This module provides components for tracking pipeline operations and
synchronizing state with the HackAgent backend API. It includes:

- Tracker: Main tracking class for per-goal result tracking (recommended)
- StepTracker: Step-level tracking for pipeline steps
- track_step: Context manager for tracking individual steps
- track_operation: Decorator for automatic operation tracking
- TrackingContext: Shared context for tracking state
- Context: Context for tracking a single goal's attack execution

The tracking system is designed to be:
- Modular: Each component has a single responsibility
- Reusable: Works with any attack or pipeline implementation
- Optional: Gracefully degrades when tracking is disabled
- Thread-safe: Safe for concurrent operations

Result Organization:
- Tracker: Creates one Result per goal/datapoint, with multiple Traces
  capturing the full attack journey (preferred for attack techniques)
- StepTracker: Creates traces for pipeline steps (useful for high-level tracking)

The Tracker approach ensures each Result represents a meaningful datapoint
(e.g., one attack goal) rather than individual LLM interactions.

Layout:
- :mod:`~hackagent.tracking.goals`: ``Tracker`` and the per-goal ``Context``
- :mod:`~hackagent.tracking.steps`: ``StepTracker``, ``TrackingContext`` and
  the tracking decorators
- :mod:`~hackagent.tracking.sinks`: ``RunSink``, event listeners and audit
  failure helpers
- :mod:`~hackagent.tracking.coordinator`: ``TrackingCoordinator``, which
  drives both levels for a technique
- :mod:`~hackagent.tracking.serialize`: JSON-safe cleaning of trace content
"""

from hackagent.tracking.steps.context import TrackingContext
from hackagent.tracking.coordinator import TrackingCoordinator
from hackagent.tracking.steps.decorators import track_operation, track_pipeline
from hackagent.tracking.sinks.listeners import BusListener, EventListener, Fanout
from hackagent.tracking.sinks.sink import RunSink
from hackagent.tracking.steps.tracker import StepTracker
from hackagent.tracking.goals.tracker import Context, Tracker

__all__ = [
    "BusListener",
    "Context",
    "EventListener",
    "Fanout",
    "RunSink",
    "StepTracker",
    "Tracker",
    "TrackingContext",
    "TrackingCoordinator",
    "track_operation",
    "track_pipeline",
]
