# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for tracking decorators."""

import unittest
from unittest.mock import MagicMock, patch

from hackagent.router.tracking.decorators import (
    track_operation,
    track_method,
    track_pipeline,
    _default_extract_input,
)
from hackagent.router.tracking.step import StepTracker
from hackagent.router.tracking.context import TrackingContext


class TestTrackOperation(unittest.TestCase):
    """Test track_operation decorator."""

    def test_track_operation_without_tracker(self):
        """Test that function runs normally without tracker."""

        @track_operation("Test Step", "TEST_STEP")
        def my_function(data, tracker=None):
            return data * 2

        result = my_function(5)
        self.assertEqual(result, 10)

    def test_track_operation_with_none_tracker(self):
        """Test that function runs normally with None tracker."""

        @track_operation("Test Step", "TEST_STEP")
        def my_function(data, tracker=None):
            return data * 2

        result = my_function(5, tracker=None)
        self.assertEqual(result, 10)

    def test_track_operation_with_non_tracker_object(self):
        """Test that function runs with non-StepTracker object."""

        @track_operation("Test Step", "TEST_STEP")
        def my_function(data, tracker=None):
            return data * 2

        result = my_function(5, tracker="not a tracker")
        self.assertEqual(result, 10)

    @patch.object(StepTracker, "track_step")
    def test_track_operation_with_valid_tracker(self, mock_track_step):
        """Test that function is tracked with valid tracker."""
        mock_client = MagicMock()
        context = TrackingContext(
            client=mock_client,
            run_id="12345678-1234-1234-1234-123456789abc",
            parent_result_id="87654321-4321-4321-4321-cba987654321",
        )
        tracker = StepTracker(context)

        # Make track_step a context manager that yields
        mock_track_step.return_value.__enter__ = MagicMock(return_value=None)
        mock_track_step.return_value.__exit__ = MagicMock(return_value=False)

        @track_operation("Test Step", "TEST_STEP")
        def my_function(data, tracker=None):
            return data * 2

        result = my_function(5, tracker=tracker)

        self.assertEqual(result, 10)
        mock_track_step.assert_called_once()

    def test_track_operation_with_custom_extractors(self):
        """Test track_operation with custom input/config extractors."""

        def extract_input(args, kwargs):
            return {"custom_input": kwargs.get("data")}

        def extract_config(args, kwargs):
            return {"custom_config": True}

        @track_operation(
            "Test Step",
            "TEST_STEP",
            extract_input=extract_input,
            extract_config=extract_config,
        )
        def my_function(data, tracker=None):
            return data * 2

        result = my_function(data=5)
        self.assertEqual(result, 10)

    @patch.object(StepTracker, "track_step")
    def test_track_operation_extractor_error_handling(self, mock_track_step):
        """Test that extractor errors are handled gracefully."""
        mock_client = MagicMock()
        context = TrackingContext(
            client=mock_client,
            run_id="12345678-1234-1234-1234-123456789abc",
        )
        tracker = StepTracker(context)

        mock_track_step.return_value.__enter__ = MagicMock(return_value=None)
        mock_track_step.return_value.__exit__ = MagicMock(return_value=False)

        def bad_extractor(args, kwargs):
            raise ValueError("Extractor error")

        @track_operation("Test Step", "TEST_STEP", extract_input=bad_extractor)
        def my_function(data, tracker=None):
            return data * 2

        # Should not raise, just log warning
        result = my_function(5, tracker=tracker)
        self.assertEqual(result, 10)


class TestDefaultExtractInput(unittest.TestCase):
    """Test _default_extract_input helper function."""

    def test_extract_goals_from_kwargs(self):
        """Test extracting goals from kwargs."""
        kwargs = {"goals": ["goal1", "goal2", "goal3"]}
        result = _default_extract_input((), kwargs)

        self.assertIsNotNone(result)
        self.assertEqual(result["goals"], ["goal1", "goal2", "goal3"])

    def test_extract_goals_samples_large_list(self):
        """Test that large lists are sampled."""
        goals = [f"goal{i}" for i in range(10)]
        kwargs = {"goals": goals}
        result = _default_extract_input((), kwargs)

        self.assertIsNotNone(result)
        self.assertEqual(len(result["goals"]), 5)  # Sampled to first 5

    def test_extract_targets_from_kwargs(self):
        """Test extracting targets from kwargs."""
        kwargs = {"targets": ["target1", "target2"]}
        result = _default_extract_input((), kwargs)

        self.assertIsNotNone(result)
        self.assertEqual(result["targets"], ["target1", "target2"])

    def test_extract_inputs_from_kwargs(self):
        """Test extracting inputs from kwargs."""
        kwargs = {"inputs": ["input1", "input2"]}
        result = _default_extract_input((), kwargs)

        self.assertIsNotNone(result)
        self.assertEqual(result["inputs"], ["input1", "input2"])

    def test_no_matching_keys(self):
        """Test when no matching keys are found."""
        kwargs = {"other_param": "value"}
        result = _default_extract_input((), kwargs)

        self.assertIsNone(result)

    def test_extract_dataframe_from_kwargs(self):
        """Test extracting DataFrame-like object from kwargs."""
        # Mock a DataFrame-like object
        mock_df = MagicMock()
        mock_df.head.return_value.to_dict.return_value = {"col": [1, 2, 3]}

        kwargs = {"input_df": mock_df}
        result = _default_extract_input((), kwargs)

        self.assertIsNotNone(result)
        self.assertEqual(result["input_sample"], {"col": [1, 2, 3]})

    def test_extract_dataframe_from_args(self):
        """Test extracting DataFrame-like object from positional args."""
        mock_df = MagicMock()
        mock_df.head.return_value.to_dict.return_value = {"col": [1, 2]}

        result = _default_extract_input((mock_df,), {})

        self.assertIsNotNone(result)
        self.assertEqual(result["input_sample"], {"col": [1, 2]})


class TestTrackMethod(unittest.TestCase):
    """Test track_method decorator."""

    def test_track_method_without_tracker(self):
        """Test method runs normally without tracker."""

        class MyClass:
            @track_method("Test Step", "TEST_STEP")
            def my_method(self, data):
                return data * 2

        obj = MyClass()
        result = obj.my_method(5)
        self.assertEqual(result, 10)

    def test_track_method_with_none_tracker(self):
        """Test method runs normally when self.tracker is None."""

        class MyClass:
            def __init__(self):
                self.tracker = None

            @track_method("Test Step", "TEST_STEP")
            def my_method(self, data):
                return data * 2

        obj = MyClass()
        result = obj.my_method(5)
        self.assertEqual(result, 10)

    @patch.object(StepTracker, "track_step")
    def test_track_method_with_valid_tracker(self, mock_track_step):
        """Test method is tracked with valid tracker."""
        mock_client = MagicMock()
        context = TrackingContext(
            client=mock_client,
            run_id="12345678-1234-1234-1234-123456789abc",
        )
        tracker = StepTracker(context)

        mock_track_step.return_value.__enter__ = MagicMock(return_value=None)
        mock_track_step.return_value.__exit__ = MagicMock(return_value=False)

        class MyClass:
            def __init__(self, tracker):
                self.tracker = tracker

            @track_method("Test Step", "TEST_STEP")
            def my_method(self, data):
                return data * 2

        obj = MyClass(tracker)
        result = obj.my_method(5)

        self.assertEqual(result, 10)
        mock_track_step.assert_called_once()


class TestTrackPipeline(unittest.TestCase):
    """Test track_pipeline class decorator."""

    def test_track_pipeline_basic(self):
        """Test basic track_pipeline decoration."""

        @track_pipeline(tracker_param="tracker")
        class MyPipeline:
            def __init__(self, tracker=None):
                self.tracker = tracker

            def process(self, data, tracker=None):
                return data * 2

            def transform(self, data, tracker=None):
                return data + 1

        pipeline = MyPipeline()

        # Methods should still work
        self.assertEqual(pipeline.process(5), 10)
        self.assertEqual(pipeline.transform(5), 6)

    def test_track_pipeline_injects_tracker(self):
        """Test that tracker is injected from self."""

        @track_pipeline(tracker_param="tracker")
        class MyPipeline:
            def __init__(self, tracker=None):
                self.tracker = tracker

            def process(self, data, tracker=None):
                # Return tracker to verify injection
                return tracker

        mock_tracker = MagicMock()
        pipeline = MyPipeline(tracker=mock_tracker)

        result = pipeline.process(5)
        self.assertEqual(result, mock_tracker)

    def test_track_pipeline_preserves_private_methods(self):
        """Test that private methods are not wrapped."""

        @track_pipeline(tracker_param="tracker")
        class MyPipeline:
            def __init__(self):
                pass

            def _private_method(self, data, tracker=None):
                return data

            def public_method(self, data, tracker=None):
                return data

        pipeline = MyPipeline()
        # Both should work
        self.assertEqual(pipeline._private_method(5), 5)
        self.assertEqual(pipeline.public_method(5), 5)


if __name__ == "__main__":
    unittest.main()
