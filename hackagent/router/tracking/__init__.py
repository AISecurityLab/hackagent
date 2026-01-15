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

- StepTracker: Main tracking class for managing operation lifecycle
- track_step: Context manager for tracking individual steps
- track_operation: Decorator for automatic operation tracking
- TrackingContext: Shared context for tracking state

The tracking system is designed to be:
- Modular: Each component has a single responsibility
- Reusable: Works with any attack or pipeline implementation
- Optional: Gracefully degrades when tracking is disabled
- Thread-safe: Safe for concurrent operations
"""

from .context import TrackingContext
from .decorators import track_operation, track_pipeline
from .tracker import StepTracker

__all__ = [
    "StepTracker",
    "TrackingContext",
    "track_operation",
    "track_pipeline",
]
