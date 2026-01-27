# Copyright 2025 - AI4I. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
"""

from .context import TrackingContext
from .decorators import track_operation, track_pipeline
from .step import StepTracker
from .tracker import Context, Tracker

__all__ = [
    "Context",
    "StepTracker",
    "Tracker",
    "TrackingContext",
    "track_operation",
    "track_pipeline",
]
