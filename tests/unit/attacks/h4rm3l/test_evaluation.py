# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for h4rm3l evaluation module."""

import logging
import unittest
from unittest.mock import MagicMock

from hackagent.attacks.techniques.h4rm3l.evaluation import H4rm3lEvaluation


class TestH4rm3lEvaluation(unittest.TestCase):
    def _make_eval(self, config=None):
        return H4rm3lEvaluation(
            config=config or {"h4rm3l_params": {}, "judges": [], "filter_len": 10},
            logger=logging.getLogger("test"),
            client=MagicMock(),
        )

    def test_empty_input(self):
        ev = self._make_eval()
        self.assertEqual(ev.execute([]), [])

    def test_error_items_marked_failed(self):
        ev = self._make_eval()
        data = [
            {
                "goal": "test",
                "error": "decoration failed",
                "response": None,
                "full_prompt": None,
            }
        ]
        result = ev.execute(data)
        self.assertFalse(result[0]["success"])
        self.assertEqual(result[0]["best_score"], 0.0)
        self.assertIn("evaluation_notes", result[0])

    def test_preserves_original_data(self):
        ev = self._make_eval()
        data = [
            {
                "goal": "test goal",
                "error": "failed",
                "response": None,
                "full_prompt": None,
                "program": "IdentityDecorator()",
            }
        ]
        result = ev.execute(data)
        self.assertEqual(result[0]["goal"], "test goal")
        self.assertEqual(result[0]["program"], "IdentityDecorator()")


if __name__ == "__main__":
    unittest.main()
