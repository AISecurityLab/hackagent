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

"""Tests for shared progress bar utilities."""

import os
import unittest
from unittest.mock import patch

from hackagent.attacks.shared.progress import (
    create_progress_bar,
    NullProgress,
)


class TestNullProgress(unittest.TestCase):
    """Test NullProgress class."""

    def test_add_task_returns_zero(self):
        """Test that add_task returns 0."""
        progress = NullProgress()
        result = progress.add_task("Test task", total=100)
        self.assertEqual(result, 0)

    def test_update_does_nothing(self):
        """Test that update doesn't raise."""
        progress = NullProgress()
        # Should not raise
        progress.update(0, advance=1)

    def test_context_manager(self):
        """Test that NullProgress works as context manager."""
        progress = NullProgress()
        with progress as p:
            self.assertIs(p, progress)


class TestCreateProgressBar(unittest.TestCase):
    """Test create_progress_bar function."""

    @patch.dict(os.environ, {"NO_COLOR": "1"})
    def test_returns_null_progress_in_tui_mode(self):
        """Test that TUI mode returns NullProgress."""
        with create_progress_bar("Test", 10) as (progress, task):
            self.assertIsInstance(progress, NullProgress)
            self.assertEqual(task, 0)

    @patch.dict(os.environ, {"NO_COLOR": "1"})
    def test_null_progress_can_be_updated(self):
        """Test that NullProgress can be updated without error."""
        with create_progress_bar("Test", 10) as (progress, task):
            # Should not raise
            for _ in range(10):
                progress.update(task, advance=1)

    @patch.dict(os.environ, {}, clear=True)
    def test_returns_rich_progress_in_normal_mode(self):
        """Test that normal mode returns Rich Progress."""
        # Remove NO_COLOR if it exists
        os.environ.pop("NO_COLOR", None)

        with create_progress_bar("Test", 5) as (progress, task):
            # Should be a Rich Progress instance, not NullProgress
            self.assertNotIsInstance(progress, NullProgress)
            # Task should be valid task ID
            self.assertIsNotNone(task)


if __name__ == "__main__":
    unittest.main()
