# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for the post-event-bus TUI changes:

- Filtering / search helpers on :class:`AttackLogViewer`.
- :class:`AgentActionsViewer` event-bus translation
  (``trace_added``, ``goal_started``, ``goal_finalized``).
- :class:`hackagent.router.tracking.Tracker` emits structured events when
  given an ``event_bus``.
- :class:`hackagent.router.tracking.StepTracker` emits ``step_started`` /
  ``step_ended`` even when backend tracking is disabled.
"""

from typing import Any, List
from unittest.mock import MagicMock

import pytest

from hackagent.cli.tui.events import (
    EVENT_GOAL_FINALIZED,
    EVENT_GOAL_STARTED,
    EVENT_STEP_ENDED,
    EVENT_STEP_STARTED,
    TUIEvent,
    TUIEventBus,
)
from hackagent.cli.tui.widgets.logs import AttackLogViewer


# ============================================================================
# AttackLogViewer filtering / search helpers
# ============================================================================


class TestAttackLogViewerFilters:
    """Test the pure logic in the new filter / search pipeline."""

    def _make_viewer(self) -> AttackLogViewer:
        # No mount — we only exercise helper methods that don't touch widgets.
        return AttackLogViewer()

    def test_format_record_color_per_level(self) -> None:
        v = self._make_viewer()
        assert "[cyan]" in v._format_record("INFO", "x")
        assert "[bold red]" in v._format_record("ERROR", "x")
        assert "[yellow]" in v._format_record("WARNING", "x")
        assert "[dim]" in v._format_record("DEBUG", "x")

    def test_format_record_header_passthrough(self) -> None:
        v = self._make_viewer()
        banner = "\n[bold magenta]══[/bold magenta]\n"
        # HEADER must be returned verbatim (pre-formatted Rich markup).
        assert v._format_record("HEADER", banner) is banner

    def test_record_visible_respects_level_toggle(self) -> None:
        v = self._make_viewer()
        assert v._record_visible("INFO", "msg") is True
        v._level_enabled["INFO"] = False
        assert v._record_visible("INFO", "msg") is False

    def test_critical_filtered_with_error_toggle(self) -> None:
        """CRITICAL collapses to ERROR for filter purposes."""
        v = self._make_viewer()
        v._level_enabled["ERROR"] = False
        assert v._record_visible("CRITICAL", "boom") is False

    def test_header_ignores_level_filter(self) -> None:
        v = self._make_viewer()
        # Mute every level.
        for k in v._level_enabled:
            v._level_enabled[k] = False
        # HEADER still passes.
        assert v._record_visible("HEADER", "banner") is True

    def test_search_query_case_insensitive_substring(self) -> None:
        v = self._make_viewer()
        v._search_query = "harm"
        assert v._record_visible("INFO", "Running HARMBench eval") is True
        assert v._record_visible("INFO", "unrelated message") is False

    def test_search_applies_to_headers_too(self) -> None:
        v = self._make_viewer()
        v._search_query = "step 2"
        assert v._record_visible("HEADER", "🎯 STEP 1: Generation") is False
        assert v._record_visible("HEADER", "🎯 STEP 2: Evaluation") is True

    def test_filtered_plaintext_strips_markup_from_headers(self) -> None:
        v = self._make_viewer()
        v._records.append(
            ("HEADER", "\n[bold magenta]─\n🎯 STEP 1: Generation\n─[/bold magenta]\n")
        )
        v._records.append(("INFO", "info line"))
        text = v._filtered_plaintext()
        assert "[bold magenta]" not in text
        assert "🎯 STEP 1: Generation" in text
        assert "[INFO] info line" in text

    def test_filtered_plaintext_respects_search(self) -> None:
        v = self._make_viewer()
        v._records.extend([("INFO", "alpha"), ("INFO", "beta"), ("INFO", "gamma")])
        v._search_query = "bet"
        text = v._filtered_plaintext()
        assert "beta" in text
        assert "alpha" not in text
        assert "gamma" not in text

    def test_save_logs_to_file_returns_none_when_empty(self) -> None:
        v = self._make_viewer()
        assert v.save_logs_to_file() is None

    def test_save_logs_to_file_writes_filtered_content(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import tempfile

        v = self._make_viewer()
        v._records.append(("INFO", "kept"))
        v._records.append(("DEBUG", "muted"))
        v._level_enabled["DEBUG"] = False

        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
        path = v.save_logs_to_file()
        assert path is not None
        assert path.startswith(str(tmp_path))
        content = open(path).read()
        assert "kept" in content
        assert "muted" not in content


# ============================================================================
# AgentActionsViewer bus subscription — exercise the dispatcher directly
# ============================================================================


class _StubViewer:
    """Stand-in for :class:`AgentActionsViewer`.

    The real viewer requires a mounted Textual app; we only need to verify
    that :meth:`_handle_event` invokes the right ``add_*`` helpers.
    """

    def __init__(self) -> None:
        self.calls: List[tuple] = []
        self._action_count = 0

    def add_step_separator(self, name: str, number: int = 0) -> None:
        self.calls.append(("step", name, number))

    def add_tool_call(
        self, tool_name: str, arguments=None, result=None, step_number=None
    ) -> None:
        self.calls.append(("tool", tool_name, arguments, result, step_number))

    def add_info_message(self, msg: str) -> None:
        self.calls.append(("info", msg))

    def update_action_count(self, n: int) -> None:
        self.calls.append(("count", n))

    def query_one(self, *_a, **_kw):  # pragma: no cover - only used by other paths
        return MagicMock()


def _dispatch(viewer: _StubViewer, event_type: str, **payload: Any) -> None:
    """Invoke the viewer's `_handle_event` method (bound to a real viewer).

    We also bind ``_render_trace`` so the stub can resolve the call without
    instantiating a real Textual widget.
    """
    from hackagent.cli.tui.widgets.actions import AgentActionsViewer

    # Bind unbound methods to our stub so `self._render_trace(...)` resolves.
    viewer._render_trace = AgentActionsViewer._render_trace.__get__(viewer)
    AgentActionsViewer._handle_event(viewer, TUIEvent(event_type, payload, 0.0))


class TestAgentActionsViewerDispatch:
    """The dispatcher must translate bus events into the right add_* calls."""

    def test_step_started_adds_separator(self) -> None:
        v = _StubViewer()
        _dispatch(v, EVENT_STEP_STARTED, step_name="Generation")
        assert any(c[0] == "step" and c[1] == "Generation" for c in v.calls)

    def test_goal_started_adds_separator_with_number(self) -> None:
        v = _StubViewer()
        _dispatch(
            v,
            EVENT_GOAL_STARTED,
            goal_index=2,
            goal="Test prompt",
            attack_type="advprefix",
        )
        step_calls = [c for c in v.calls if c[0] == "step"]
        assert len(step_calls) == 1
        name, number = step_calls[0][1], step_calls[0][2]
        assert "Goal #3" in name  # 0-based index → 1-based label
        assert "ADVPREFIX" in name
        assert number == 3

    def test_trace_added_tool_call_maps_to_add_tool_call(self) -> None:
        v = _StubViewer()
        _dispatch(
            v,
            "trace_added",
            step_type="TOOL_CALL",
            step_name="Call",
            sequence=5,
            content={"name": "grep", "arguments": {"pattern": "foo"}},
        )
        tool_calls = [c for c in v.calls if c[0] == "tool"]
        assert tool_calls == [("tool", "grep", {"pattern": "foo"}, None, 5)]

    def test_trace_added_tool_response_maps_to_add_tool_call_with_result(self) -> None:
        v = _StubViewer()
        _dispatch(
            v,
            "trace_added",
            step_type="TOOL_RESPONSE",
            step_name="Result",
            sequence=6,
            content={"tool": "grep", "result": "matched 3 lines"},
        )
        tool_calls = [c for c in v.calls if c[0] == "tool"]
        assert len(tool_calls) == 1
        _, name, args, result, step_number = tool_calls[0]
        assert name == "grep"
        assert args is None
        assert "matched 3 lines" in result
        assert step_number == 6


# ============================================================================
# Tracker / StepTracker event emission
# ============================================================================


class TestTrackerEmitsEvents:
    """`Tracker` should publish goal lifecycle events on the bus."""

    def test_create_goal_result_emits_goal_started_without_backend(self) -> None:
        from hackagent.router.tracking.tracker import Tracker

        bus = TUIEventBus()
        received: List[TUIEvent] = []
        bus.subscribe(received.append, event_type=EVENT_GOAL_STARTED)

        tracker = Tracker(
            backend=None,
            run_id=None,
            logger=MagicMock(),
            attack_type="advprefix",
            event_bus=bus,
        )
        tracker.create_goal_result(goal="Test goal", goal_index=0)

        assert len(received) == 1
        payload = received[0].payload
        assert payload["goal"] == "Test goal"
        assert payload["goal_index"] == 0
        assert payload["attack_type"] == "advprefix"

    def test_finalize_goal_emits_goal_finalized(self) -> None:
        from hackagent.router.tracking.tracker import Tracker

        bus = TUIEventBus()
        received: List[TUIEvent] = []
        bus.subscribe(received.append, event_type=EVENT_GOAL_FINALIZED)

        tracker = Tracker(
            backend=None,
            run_id=None,
            logger=MagicMock(),
            attack_type="advprefix",
            event_bus=bus,
        )
        ctx = tracker.create_goal_result(goal="Test", goal_index=0)
        tracker.finalize_goal(ctx, success=True, evaluation_notes="ok")

        assert len(received) == 1
        payload = received[0].payload
        assert payload["goal_index"] == 0
        assert payload["success"] is True
        assert payload["evaluation_notes"] == "ok"

    def test_tracker_without_bus_does_not_raise(self) -> None:
        """Backwards compat: omitting event_bus must keep working."""
        from hackagent.router.tracking.tracker import Tracker

        tracker = Tracker(
            backend=None,
            run_id=None,
            logger=MagicMock(),
            attack_type="x",
        )
        ctx = tracker.create_goal_result(goal="g", goal_index=0)
        tracker.finalize_goal(ctx, success=False)


class TestStepTrackerEmitsEvents:
    """`StepTracker.track_step` should emit step_started/step_ended."""

    def test_track_step_emits_lifecycle_when_disabled(self) -> None:
        from hackagent.router.tracking.context import TrackingContext
        from hackagent.router.tracking.step import StepTracker

        bus = TUIEventBus()
        received: List[TUIEvent] = []
        bus.subscribe(received.append)

        ctx = TrackingContext.create_disabled()
        ctx.event_bus = bus
        tracker = StepTracker(ctx)

        with tracker.track_step("Generate", "STEP_GEN"):
            pass

        types = [e.event_type for e in received]
        assert types == [EVENT_STEP_STARTED, EVENT_STEP_ENDED]
        assert received[0].payload["step_name"] == "Generate"
        assert received[1].payload["success"] is True

    def test_track_step_emits_step_ended_on_failure(self) -> None:
        from hackagent.router.tracking.context import TrackingContext
        from hackagent.router.tracking.step import StepTracker

        bus = TUIEventBus()
        received: List[TUIEvent] = []
        bus.subscribe(received.append, event_type=EVENT_STEP_ENDED)

        ctx = TrackingContext.create_disabled()
        ctx.event_bus = bus
        tracker = StepTracker(ctx)

        with pytest.raises(RuntimeError):
            with tracker.track_step("Failing", "STEP_X"):
                raise RuntimeError("boom")

        assert len(received) == 1
        assert received[0].payload["success"] is False
        assert "boom" in received[0].payload["error"]


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
