# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for flowchart text serializers — verify all formats handle all layouts."""

import unittest

from hackagent.attacks.techniques.fc.flowchart_renderer import (
    TEXT_FORMAT_SERIALIZERS,
    steps_to_ascii,
    steps_to_dot,
    steps_to_mermaid,
    steps_to_plantuml,
    steps_to_tikz,
)

GOAL = "Perform the task"
STEPS = [
    "Gather materials",
    "Mix ingredients",
    "Heat solution",
    "Filter result",
    "Dry product",
]
LAYOUTS = ["vertical", "horizontal", "tortuous"]


class TestSerializerLayoutSupport(unittest.TestCase):
    """Every serializer must produce non-empty output for every layout."""

    def test_all_formats_registered(self):
        expected = {"dot", "mermaid", "tikz", "plantuml", "ascii"}
        self.assertEqual(set(TEXT_FORMAT_SERIALIZERS.keys()), expected)

    def test_all_serializers_callable(self):
        for name, fn in TEXT_FORMAT_SERIALIZERS.items():
            self.assertTrue(callable(fn), f"{name} serializer is not callable")


class TestMermaidLayouts(unittest.TestCase):
    def test_vertical(self):
        result = steps_to_mermaid(GOAL, STEPS, "vertical")
        self.assertIn("flowchart TD", result)
        self.assertIn("goal", result)
        self.assertIn("step1", result)
        self.assertIn("-->", result)

    def test_horizontal(self):
        result = steps_to_mermaid(GOAL, STEPS, "horizontal")
        self.assertIn("flowchart LR", result)
        self.assertIn("-->", result)

    def test_tortuous(self):
        result = steps_to_mermaid(GOAL, STEPS, "tortuous")
        # Uses block-beta diagram with columns for S-shape
        self.assertIn("block-beta", result)
        self.assertIn("columns", result)
        self.assertIn("-->", result)

    def test_s_shaped_alias(self):
        result = steps_to_mermaid(GOAL, STEPS, "s_shaped")
        self.assertIn("block-beta", result)


class TestTikZLayouts(unittest.TestCase):
    def test_vertical(self):
        result = steps_to_tikz(GOAL, STEPS, "vertical")
        self.assertIn("below of", result)
        self.assertIn(r"\begin{tikzpicture}", result)
        self.assertIn(r"\end{tikzpicture}", result)
        self.assertIn(r"\draw[arrow]", result)

    def test_horizontal(self):
        result = steps_to_tikz(GOAL, STEPS, "horizontal")
        self.assertIn("right of", result)
        self.assertNotIn("below of", result)

    def test_tortuous(self):
        result = steps_to_tikz(GOAL, STEPS, "tortuous")
        # Tortuous uses both right of and left of for alternating rows
        self.assertIn("right of", result)
        self.assertIn("left of", result)
        self.assertIn("below of", result)
        self.assertIn(r"\draw[arrow]", result)

    def test_s_shaped_alias(self):
        result = steps_to_tikz(GOAL, STEPS, "s_shaped")
        self.assertIn("left of", result)


class TestPlantUMLLayouts(unittest.TestCase):
    def test_vertical(self):
        result = steps_to_plantuml(GOAL, STEPS, "vertical")
        self.assertIn("@startuml", result)
        self.assertIn("@enduml", result)
        self.assertIn("-d->", result)
        self.assertIn("usecase", result)

    def test_horizontal(self):
        result = steps_to_plantuml(GOAL, STEPS, "horizontal")
        self.assertIn("@startuml", result)
        self.assertIn("-r->", result)

    def test_tortuous(self):
        result = steps_to_plantuml(GOAL, STEPS, "tortuous")
        self.assertIn("@startuml", result)
        self.assertIn("@enduml", result)
        # Uses directional arrows for S-shaped layout
        self.assertIn("-r->", result)
        self.assertIn("-l->", result)
        self.assertIn("-d->", result)

    def test_s_shaped_alias(self):
        result = steps_to_plantuml(GOAL, STEPS, "s_shaped")
        self.assertIn("-l->", result)


class TestASCIILayouts(unittest.TestCase):
    def test_vertical(self):
        result = steps_to_ascii(GOAL, STEPS, "vertical")
        # Vertical has downward arrows
        self.assertIn("|", result)
        self.assertIn("v", result)
        # No horizontal arrows
        self.assertNotIn("-->", result)

    def test_horizontal(self):
        result = steps_to_ascii(GOAL, STEPS, "horizontal")
        self.assertIn("-->", result)
        # Boxes are side by side, no downward arrows between them
        lines = result.split("\n")
        # All content on a few rows (compact)
        self.assertLess(len(lines), 15)

    def test_tortuous(self):
        result = steps_to_ascii(GOAL, STEPS, "tortuous")
        # Has both horizontal arrows and vertical connectors
        self.assertIn("-->", result)
        self.assertIn("v", result)


class TestDOTLayouts(unittest.TestCase):
    def test_vertical(self):
        result = steps_to_dot(GOAL, STEPS, "vertical")
        self.assertIn("digraph", result)
        self.assertNotIn("rankdir=LR", result)
        self.assertIn("->", result)

    def test_horizontal(self):
        result = steps_to_dot(GOAL, STEPS, "horizontal")
        self.assertIn("rankdir=LR", result)
        self.assertIn("->", result)

    def test_tortuous(self):
        result = steps_to_dot(GOAL, STEPS, "tortuous")
        self.assertIn("digraph", result)
        self.assertIn("rank=same", result)
        self.assertIn("->", result)

    def test_s_shaped_alias(self):
        result = steps_to_dot(GOAL, STEPS, "s_shaped")
        self.assertIn("rank=same", result)


class TestAllFormatsAllLayouts(unittest.TestCase):
    """Parametric test: every format × every layout produces non-empty string."""

    def test_all_combinations(self):
        for fmt_name, serializer_fn in TEXT_FORMAT_SERIALIZERS.items():
            for layout in LAYOUTS:
                with self.subTest(format=fmt_name, layout=layout):
                    result = serializer_fn(GOAL, STEPS, layout)
                    self.assertIsInstance(result, str)
                    self.assertGreater(
                        len(result),
                        50,
                        f"{fmt_name}/{layout} produced too-short output",
                    )
                    # All steps should be mentioned
                    for step in STEPS:
                        self.assertIn(
                            step,
                            result,
                            f"Step '{step}' missing in {fmt_name}/{layout}",
                        )


if __name__ == "__main__":
    unittest.main()
