# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the eval command rendering helpers."""

import unittest
from unittest.mock import MagicMock, patch

from hackagent.cli.commands.attack import display as display_mod
from hackagent.cli.commands.attack.display import (
    _display_advprefix_info,
    _display_attack_results,
    _display_attack_summary,
    _display_generic_attack_info,
)


class _FakeColumn(list):
    """Minimal stand-in for a DataFrame column."""

    def __init__(self, values, dtype="float64"):
        super().__init__(values)
        self.dtype = dtype

    def mean(self):
        return sum(self) / len(self)


class _FakeFrame:
    """Duck-typed DataFrame: enough surface for the display helper."""

    def __init__(self, columns, rows=1, empty=False):
        self.columns = columns
        self._rows = rows
        self.empty = empty
        self._data = {name: _FakeColumn([1.0] * rows) for name in columns}

    def __len__(self):
        return self._rows

    def __getitem__(self, key):
        if isinstance(key, list):
            return _FakeFrame(key, self._rows)
        return self._data[key]

    def head(self):
        return self


def _printed(printer):
    return " ".join(str(call.args[0]) for call in printer.call_args_list if call.args)


class TestDisplayGenericAttackInfo(unittest.TestCase):
    def test_catalog_metadata_is_rendered(self):
        with patch.object(display_mod.console, "print") as printer:
            _display_generic_attack_info("tap")

        panel = printer.call_args.args[0]
        self.assertIn("TAP", str(panel.title))
        self.assertIn("hackagent eval tap", panel.renderable)
        self.assertIn("Tree of Attacks", panel.renderable)

    def test_unknown_strategy_raises(self):
        with self.assertRaises(KeyError):
            _display_generic_attack_info("nonexistent")


class TestDisplayAttackSummary(unittest.TestCase):
    def test_core_fields_are_rendered(self):
        with patch.object(display_mod.console, "print") as printer:
            _display_attack_summary(
                "bot", "litellm", "http://x", "goal one", {"attack_type": "tap"}
            )

        panel = printer.call_args.args[0]
        self.assertIn("bot", panel.renderable)
        self.assertIn("http://x", panel.renderable)
        self.assertIn("tap", panel.renderable)
        self.assertNotIn("Additional Config", panel.renderable)

    def test_extra_configuration_is_counted(self):
        with patch.object(display_mod.console, "print") as printer:
            _display_attack_summary(
                "bot",
                "litellm",
                "http://x",
                "goal",
                {"attack_type": "tap", "goals": ["g"], "judges": [], "timeout": 10},
            )

        self.assertIn("2 parameters loaded", printer.call_args.args[0].renderable)


class TestDisplayAttackResults(unittest.TestCase):
    def _render(self, results):
        with patch.object(display_mod.console, "print") as printer:
            _display_attack_results(results)
        return printer

    def test_empty_list_reports_zero_entries(self):
        printed = _printed(self._render([]))

        self.assertIn("Generated 0 result entries", printed)

    def test_list_of_dicts_reports_sample_fields(self):
        printed = _printed(self._render([{"goal": "g", "prefix": "p", "eval_hb": 0}]))

        self.assertIn("Sample fields", printed)
        self.assertIn("goal", printed)
        self.assertIn("No successful jailbreaks detected", printed)

    def test_successful_jailbreaks_are_counted_from_either_judge(self):
        printed = _printed(
            self._render([{"eval_hb": 1}, {"eval_jb": 1}, {"eval_hb": 0}])
        )

        self.assertIn("Successful jailbreaks: 2/3", printed)

    def test_list_of_non_dicts_skips_field_analysis(self):
        printed = _printed(self._render(["a", "b"]))

        self.assertIn("Generated 2 result entries", printed)
        self.assertNotIn("Sample fields", printed)

    def test_dataframe_like_results_render_a_metrics_table(self):
        frame = _FakeFrame(["goal", "prefix", "success_score"], rows=3)

        printer = self._render(frame)

        tables = [
            call.args[0]
            for call in printer.call_args_list
            if hasattr(call.args[0], "columns") and hasattr(call.args[0], "title")
        ]
        metrics = tables[0]
        self.assertEqual(metrics.title, "Key Metrics")
        self.assertIn("Avg success_score", metrics.columns[0]._cells)

    def test_empty_dataframe_only_reports_the_count(self):
        frame = _FakeFrame(["goal"], rows=0, empty=True)

        printed = _printed(self._render(frame))

        self.assertIn("Generated 0 result entries", printed)
        self.assertNotIn("Key Metrics", printed)

    def test_dataframe_without_goal_columns_falls_back_to_all_columns(self):
        frame = _FakeFrame(["score"], rows=2)

        with patch.object(display_mod, "display_results_table") as table:
            self._render(frame)

        self.assertEqual(table.call_args.args[1], "Sample Attack Results")

    def test_scalar_results_report_their_type(self):
        printed = _printed(self._render(42))

        self.assertIn("Results: int", printed)

    def test_sized_non_dataframe_results_report_a_count(self):
        printed = _printed(self._render({"a": 1, "b": 2}))

        self.assertIn("Count: 2", printed)

    def test_analysis_failures_are_reported_without_raising(self):
        broken = MagicMock()
        broken.columns = ["goal"]
        broken.empty = False
        type(broken).__len__ = MagicMock(side_effect=RuntimeError("boom"))

        printed = _printed(self._render(broken))

        self.assertIn("Could not analyze results", printed)


class TestDisplayAdvprefixInfo(unittest.TestCase):
    def test_long_form_documentation_is_rendered(self):
        with patch.object(display_mod.console, "print") as printer:
            _display_advprefix_info()

        panel = printer.call_args.args[0]
        self.assertIn("AdvPrefix Attack Information", str(panel.title))
        self.assertIn("Ethical Usage", panel.renderable)


if __name__ == "__main__":
    unittest.main()
