# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Recording stand-ins for StepTracker and TrackingCoordinator."""

from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

Call = Tuple[str, Tuple[Any, ...], Dict[str, Any]]


class RecordingStepTracker:
    """Stand-in for ``StepTracker``: records steps and step metadata."""

    def __init__(self) -> None:
        self.steps: List[Tuple[Any, ...]] = []
        self.metadata: List[Tuple[Any, Any]] = []

    @contextmanager
    def track_step(self, *args: Any, **_kwargs: Any):
        self.steps.append(args)
        yield None

    def add_step_metadata(self, key: Any, value: Any = None) -> None:
        self.metadata.append((key, value))


class RecordingCoordinator:
    """Stand-in for ``TrackingCoordinator`` that records every call.

    ``enrich_with_result_ids`` returns its input unchanged; every other
    method returns ``None``. Inspect calls with :meth:`calls_to`.
    """

    def __init__(
        self,
        goal_tracker: Optional[Any] = None,
        has_goal_tracking: bool = False,
    ) -> None:
        self.goal_tracker = goal_tracker
        self.has_goal_tracking = has_goal_tracking
        self.step_tracker = RecordingStepTracker()
        self.calls: List[Call] = []

    def calls_to(self, name: str) -> List[Tuple[Tuple[Any, ...], Dict[str, Any]]]:
        """Return ``(args, kwargs)`` for each recorded call to ``name``."""
        return [(args, kwargs) for n, args, kwargs in self.calls if n == name]

    def _record(self, name: str, args: Tuple[Any, ...], kwargs: Dict[str, Any]):
        self.calls.append((name, args, kwargs))

    def initialize_goals(self, *args: Any, **kwargs: Any) -> None:
        self._record("initialize_goals", args, kwargs)

    def initialize_goals_from_pipeline_data(self, *args: Any, **kwargs: Any) -> None:
        self._record("initialize_goals_from_pipeline_data", args, kwargs)

    def backdate_goal_start_times(self, *args: Any, **kwargs: Any) -> None:
        self._record("backdate_goal_start_times", args, kwargs)

    def enrich_with_result_ids(self, results: Any) -> Any:
        self._record("enrich_with_result_ids", (results,), {})
        return results

    def finalize_all_goals(self, *args: Any, **kwargs: Any) -> None:
        self._record("finalize_all_goals", args, kwargs)

    def finalize_pipeline(self, *args: Any, **kwargs: Any) -> None:
        self._record("finalize_pipeline", args, kwargs)

    def finalize_on_error(self, *args: Any, **kwargs: Any) -> None:
        self._record("finalize_on_error", args, kwargs)

    def log_summary(self) -> None:
        self._record("log_summary", (), {})
