import unittest
from unittest.mock import MagicMock

from hackagent.attacks.techniques.autodan_turbo.dashboard_tracing import (
    emit_phase_trace,
)


class TestDashboardTracing(unittest.TestCase):
    def test_emit_phase_trace_no_tracker_is_noop(self):
        cfg = {}
        emit_phase_trace(
            cfg,
            phase="WARMUP",
            subphase="GENERATION",
            step_name="step",
            payload={"x": 1},
        )

    def test_emit_phase_trace_uses_goal_context(self):
        tracker = MagicMock()
        ctx = MagicMock(goal="g", goal_index=0)
        tracker.get_goal_context_by_goal.return_value = ctx
        cfg = {"_tracker": tracker}

        emit_phase_trace(
            cfg,
            phase="WARMUP",
            subphase="GENERATION",
            step_name="step",
            payload={"x": 1},
            goal="g",
        )

        tracker.add_custom_trace.assert_called_once()
        kwargs = tracker.add_custom_trace.call_args.kwargs
        self.assertEqual(kwargs["step_name"], "step")
        self.assertIn("phase", kwargs["content"])
        self.assertEqual(kwargs["content"]["phase"], "WARMUP")

    def test_emit_phase_trace_uses_goal_idx_fallback(self):
        tracker = MagicMock()
        tracker.get_goal_context_by_goal.return_value = None
        ctx = MagicMock(goal="g2", goal_index=2)
        tracker.get_goal_context.return_value = ctx
        cfg = {"_tracker": tracker}

        emit_phase_trace(
            cfg,
            phase="LIFELONG",
            subphase="SCORING",
            step_name="step2",
            payload={"y": 2},
            goal_idx=2,
        )

        tracker.get_goal_context.assert_called_once_with(2)
        tracker.add_custom_trace.assert_called_once()

    def test_emit_phase_trace_returns_when_context_not_found(self):
        tracker = MagicMock()
        tracker.get_goal_context_by_goal.return_value = None
        tracker.get_goal_context.return_value = None
        cfg = {"_tracker": tracker}

        emit_phase_trace(
            cfg,
            phase="EVALUATION",
            subphase="JUDGE_SCORING",
            step_name="step3",
            payload={"z": 3},
            goal="missing",
            goal_idx=9,
        )

        tracker.add_custom_trace.assert_not_called()


if __name__ == "__main__":
    unittest.main()
