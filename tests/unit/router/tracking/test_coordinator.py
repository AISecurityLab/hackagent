# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for TrackingCoordinator scoring and empty-results finalization."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from hackagent.router.tracking.coordinator import TrackingCoordinator


class _FakeGoalTracker:
    def __init__(self, ctx):
        self.is_enabled = True
        self._ctx = ctx
        self.finalize_calls = []

    def get_goal_context(self, _goal_index):
        return self._ctx

    def finalize_goal(self, **kwargs):
        self.finalize_calls.append(kwargs)


class _FakeInitGoalTracker:
    def __init__(self):
        self.is_enabled = True
        self.created = []

    def create_goal_result(self, goal, goal_index, initial_metadata=None):
        self.created.append(
            {
                "goal": goal,
                "goal_index": goal_index,
                "initial_metadata": initial_metadata or {},
            }
        )

    def get_goal_context_by_goal(self, _goal):
        return None


class TestTrackingCoordinatorScoring(unittest.TestCase):
    """Validate default scorer support for HarmBenchVariant columns."""

    def test_default_goal_scorer_uses_eval_hbv(self):
        goal_data = [{"eval_hbv": 1}]
        self.assertTrue(TrackingCoordinator._default_goal_scorer(goal_data, 0.5))

    def test_get_best_score_uses_eval_hbv(self):
        goal_data = [{"eval_hbv": 0}, {"eval_hbv_mean": 0.75}]
        self.assertEqual(TrackingCoordinator._get_best_score(goal_data), 0.75)


class TestTrackingCoordinatorFinalization(unittest.TestCase):
    """Validate empty pipeline-result notes when intermediate traces exist."""

    def test_finalize_all_goals_empty_results_with_traces_has_specific_note(self):
        ctx = SimpleNamespace(traces=[{"step": "Execution"}], is_finalized=False)
        fake_goal_tracker = _FakeGoalTracker(ctx)

        coordinator = TrackingCoordinator(
            step_tracker=MagicMock(),
            goal_tracker=fake_goal_tracker,
            logger=MagicMock(),
        )
        coordinator._goal_indices = [0]

        coordinator.finalize_all_goals([])

        self.assertEqual(len(fake_goal_tracker.finalize_calls), 1)
        note = fake_goal_tracker.finalize_calls[0].get("evaluation_notes", "")
        self.assertIn("intermediate traces exist", note)


class TestTrackingCoordinatorDeferredInit(unittest.TestCase):
    """Validate deferred goal initialization with batched goal index offsets."""

    def test_initialize_goals_from_pipeline_data_preserves_index_offset(self):
        fake_goal_tracker = _FakeInitGoalTracker()
        coordinator = TrackingCoordinator(
            step_tracker=MagicMock(),
            goal_tracker=fake_goal_tracker,
            logger=MagicMock(),
            goal_index_start=5,
        )

        coordinator.initialize_goals_from_pipeline_data(
            pipeline_data=[
                {"goal": "g1", "elapsed_s": 0.1},
                {"goal": "g2", "elapsed_s": 0.2},
            ],
            initial_metadata={"attack_type": "h4rm3l"},
        )

        self.assertEqual(len(fake_goal_tracker.created), 2)
        self.assertEqual(fake_goal_tracker.created[0]["goal"], "g1")
        self.assertEqual(fake_goal_tracker.created[0]["goal_index"], 5)
        self.assertEqual(fake_goal_tracker.created[1]["goal"], "g2")
        self.assertEqual(fake_goal_tracker.created[1]["goal_index"], 6)

    def test_initialize_goals_without_explicit_offset_preserves_existing_start(self):
        """When omitted, goal_index_start should reuse coordinator offset."""
        fake_goal_tracker = _FakeInitGoalTracker()
        coordinator = TrackingCoordinator(
            step_tracker=MagicMock(),
            goal_tracker=fake_goal_tracker,
            logger=MagicMock(),
            goal_index_start=11,
            default_initial_metadata={
                "_goal_metadata_by_index": {
                    11: {"extra_fields": {"category": "cat-a"}},
                    12: {"extra_fields": {"category": "cat-b"}},
                }
            },
        )

        coordinator.initialize_goals(
            goals=["g1", "g2"],
            initial_metadata={"attack_type": "h4rm3l"},
        )

        self.assertEqual(len(fake_goal_tracker.created), 2)
        self.assertEqual(fake_goal_tracker.created[0]["goal_index"], 11)
        self.assertEqual(fake_goal_tracker.created[1]["goal_index"], 12)

        first_meta = fake_goal_tracker.created[0]["initial_metadata"]
        second_meta = fake_goal_tracker.created[1]["initial_metadata"]
        self.assertEqual(first_meta["extra_fields"], {"category": "cat-a"})
        self.assertEqual(second_meta["extra_fields"], {"category": "cat-b"})

    def test_initialize_goals_applies_goal_specific_metadata(self):
        """Per-goal metadata maps should merge correctly into initial metadata."""
        fake_goal_tracker = _FakeInitGoalTracker()
        coordinator = TrackingCoordinator(
            step_tracker=MagicMock(),
            goal_tracker=fake_goal_tracker,
            logger=MagicMock(),
            goal_index_start=5,
        )

        coordinator.initialize_goals(
            goals=["g1", "g2"],
            initial_metadata={
                "attack_type": "baseline",
                "_goal_metadata_by_index": {
                    5: {"extra_fields": {"category": "cat-a"}},
                },
                "_goal_metadata_by_goal": {
                    "g2": {"extra_fields": {"category": "cat-b"}},
                },
            },
            goal_index_start=5,
        )

        self.assertEqual(len(fake_goal_tracker.created), 2)

        first_meta = fake_goal_tracker.created[0]["initial_metadata"]
        second_meta = fake_goal_tracker.created[1]["initial_metadata"]

        self.assertEqual(first_meta["attack_type"], "baseline")
        self.assertEqual(
            first_meta["extra_fields"],
            {"category": "cat-a"},
        )

        self.assertEqual(second_meta["attack_type"], "baseline")
        self.assertEqual(
            second_meta["extra_fields"],
            {"category": "cat-b"},
        )

    def test_deferred_initialize_uses_default_initial_metadata_maps(self):
        """Default metadata passed at construction must survive deferred init."""
        fake_goal_tracker = _FakeInitGoalTracker()
        coordinator = TrackingCoordinator(
            step_tracker=MagicMock(),
            goal_tracker=fake_goal_tracker,
            logger=MagicMock(),
            goal_index_start=10,
            default_initial_metadata={
                "attack_type": "h4rm3l",
                "_goal_metadata_by_index": {
                    10: {"extra_fields": {"category": "cat-a"}},
                },
                "_goal_metadata_by_goal": {
                    "g2": {"extra_fields": {"category": "cat-b"}},
                },
            },
        )

        coordinator.initialize_goals_from_pipeline_data(
            pipeline_data=[
                {"goal": "g1", "elapsed_s": 0.1},
                {"goal": "g2", "elapsed_s": 0.2},
            ],
            initial_metadata={"batch_size": 8},
        )

        self.assertEqual(len(fake_goal_tracker.created), 2)

        first_meta = fake_goal_tracker.created[0]["initial_metadata"]
        second_meta = fake_goal_tracker.created[1]["initial_metadata"]

        self.assertEqual(first_meta["attack_type"], "h4rm3l")
        self.assertEqual(first_meta["batch_size"], 8)
        self.assertEqual(
            first_meta["extra_fields"],
            {"category": "cat-a"},
        )

        self.assertEqual(second_meta["attack_type"], "h4rm3l")
        self.assertEqual(second_meta["batch_size"], 8)
        self.assertEqual(
            second_meta["extra_fields"],
            {"category": "cat-b"},
        )


if __name__ == "__main__":
    unittest.main()
