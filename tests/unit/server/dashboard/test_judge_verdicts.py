# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the standardized multi-judge visualization across attack cards."""

import unittest
from unittest.mock import MagicMock, patch

from hackagent.server.dashboard.attack_cards import _shared
from hackagent.server.dashboard.attack_cards._shared import (
    JUDGE_VERDICTS_VUE_SNIPPET,
    AttackCardSharedMixin,
)


_MULTI_JUDGE_ROW = {
    "goal": "goal",
    "goal_number": 1,
    "_bucket": "jailbreak",
    "_is_multi_judge": True,
    "_goal_multi_metrics": {
        "judge_votes": {"eval_hb": 1, "eval_nj": 0},
        "judge_meta": {
            "eval_hb": {"id": 0, "name": "harmbench", "type": "Harmbench"},
            "eval_nj": {"id": 1, "name": "nuanced", "type": "Nuanced"},
        },
    },
}


class _Card(AttackCardSharedMixin):
    pass


class TestGoalJudgeVerdicts(unittest.TestCase):
    def test_renders_a_row_per_judge(self):
        card = _Card()
        with patch.object(_shared, "ui", MagicMock()) as mock_ui:
            card._render_goal_judge_verdicts(dict(_MULTI_JUDGE_ROW))

        labels = [call.args[0] for call in mock_ui.label.call_args_list]
        self.assertIn("JUDGE VERDICTS", labels)
        self.assertIn("harmbench", labels)
        self.assertIn("nuanced", labels)
        badges = [call.args[0] for call in mock_ui.badge.call_args_list]
        self.assertEqual(badges, ["JAILBREAK", "MITIGATED"])

    def test_no_op_for_single_judge_runs(self):
        card = _Card()
        row = dict(_MULTI_JUDGE_ROW, _is_multi_judge=False)
        with patch.object(_shared, "ui", MagicMock()) as mock_ui:
            card._render_goal_judge_verdicts(row)

        mock_ui.label.assert_not_called()

    def test_no_op_without_recorded_votes(self):
        card = _Card()
        row = dict(_MULTI_JUDGE_ROW, _goal_multi_metrics={"judge_votes": {}})
        with patch.object(_shared, "ui", MagicMock()) as mock_ui:
            card._render_goal_judge_verdicts(row)

        mock_ui.label.assert_not_called()

    def test_goal_card_shell_renders_verdicts_in_detail_mode(self):
        card = _Card()
        rendered: list[dict] = []
        card._render_goal_judge_verdicts = rendered.append  # type: ignore[method-assign]

        with patch.object(_shared, "ui", MagicMock()):
            with card._goal_card_shell(dict(_MULTI_JUDGE_ROW), detail_mode=True):
                pass

        self.assertEqual(len(rendered), 1)

    def test_goal_card_shell_skips_verdicts_in_compact_mode(self):
        card = _Card()
        rendered: list[dict] = []
        card._render_goal_judge_verdicts = rendered.append  # type: ignore[method-assign]

        with patch.object(_shared, "ui", MagicMock()):
            with card._goal_card_shell(dict(_MULTI_JUDGE_ROW), detail_mode=False):
                pass

        self.assertEqual(rendered, [])


class TestJudgeVerdictsTemplateIsShared(unittest.TestCase):
    """Per-step tables must reuse the single shared Vue snippet."""

    MODULES = ("_pap", "_advprefix", "_bon", "_static_template")

    def test_cards_with_per_step_tables_use_the_shared_snippet(self):
        import importlib

        for name in self.MODULES:
            module = importlib.import_module(
                f"hackagent.server.dashboard.attack_cards.{name}"
            )
            self.assertIs(
                module.JUDGE_VERDICTS_VUE_SNIPPET,
                JUDGE_VERDICTS_VUE_SNIPPET,
                msg=f"{name} does not use the shared judge verdicts snippet",
            )
