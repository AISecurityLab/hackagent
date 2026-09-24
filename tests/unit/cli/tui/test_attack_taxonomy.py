# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for taxonomy-aware TUI attack selection."""

from __future__ import annotations

import unittest

from textual.widgets.selection_list import Selection

from hackagent.interfaces.tui.views.attacks.helpers import (
    _selected_technique_keys,
    _strategy_selection_choices,
)


class TestStrategySelectionChoices(unittest.TestCase):
    def test_groups_by_primary_category_with_disabled_headers(self):
        choices = _strategy_selection_choices()
        headers = [c for c in choices if isinstance(c, Selection)]
        techniques = [c for c in choices if isinstance(c, tuple)]

        self.assertTrue(all(header.disabled for header in headers))
        self.assertEqual(
            [header.value for header in headers],
            ["_cat_static", "_cat_adaptive", "_cat_multi_turn"],
        )
        keys = [value for _, value in techniques]
        self.assertIn("baseline", keys)
        self.assertIn("pair", keys)
        self.assertIn("crescendo", keys)
        self.assertIn("rag", keys)

        mml_label = next(label for label, key in techniques if key == "mml")
        self.assertIn("multimodal", mml_label)
        tfc_label = next(label for label, key in techniques if key == "tfc")
        self.assertNotIn("multimodal", tfc_label)

    def test_focus_choices_are_plain_tuples(self):
        from hackagent.interfaces.tui.views.attacks.helpers import _strategy_focus_choices

        focus = _strategy_focus_choices()
        self.assertTrue(focus)
        self.assertTrue(all(isinstance(item, tuple) for item in focus))

    def test_selected_technique_keys_drop_headers(self):
        self.assertEqual(
            _selected_technique_keys(["_cat_static", "baseline", "pair"]),
            ["baseline", "pair"],
        )
