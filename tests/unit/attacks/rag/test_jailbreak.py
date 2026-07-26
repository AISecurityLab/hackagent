# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
import unittest

from hackagent.attacks.techniques.rag.jailbreak import (
    DEFAULT_JAILBREAK_CONFIG,
    build_jailbreak_framer,
)

LOGGER = logging.getLogger("test.rag.jailbreak")


class TestBuildJailbreakFramer(unittest.TestCase):
    def test_disabled_returns_none(self):
        self.assertIsNone(build_jailbreak_framer(DEFAULT_JAILBREAK_CONFIG, LOGGER))

    def test_non_dict_returns_none(self):
        self.assertIsNone(build_jailbreak_framer(None, LOGGER))

    def test_unsupported_technique_raises(self):
        with self.assertRaises(ValueError):
            build_jailbreak_framer(
                {"enabled": True, "technique": "does_not_exist"}, LOGGER
            )


class TestStaticTemplateFramer(unittest.TestCase):
    def test_frames_goal_with_template(self):
        framer = build_jailbreak_framer(
            {"enabled": True, "technique": "static_template"}, LOGGER
        )
        framed, metadata = framer.apply("do the bad thing")
        self.assertIn("do the bad thing", framed)
        self.assertNotEqual(framed, "do the bad thing")
        self.assertEqual(metadata["technique"], "static_template")
        self.assertEqual(metadata["template_category"], "role_play")

    def test_variant_index_rotates_templates(self):
        framer = build_jailbreak_framer(
            {
                "enabled": True,
                "technique": "static_template",
                "template_categories": ["role_play"],
            },
            LOGGER,
        )
        first, _ = framer.apply("goal", 0)
        second, _ = framer.apply("goal", 1)
        self.assertNotEqual(first, second)

    def test_string_category_is_accepted(self):
        framer = build_jailbreak_framer(
            {
                "enabled": True,
                "technique": "static_template",
                "template_categories": "hypothetical",
            },
            LOGGER,
        )
        _, metadata = framer.apply("goal")
        self.assertEqual(metadata["template_category"], "hypothetical")

    def test_category_without_plain_goal_templates_raises(self):
        with self.assertRaises(ValueError):
            build_jailbreak_framer(
                {
                    "enabled": True,
                    "technique": "static_template",
                    "template_categories": ["multi_language"],
                },
                LOGGER,
            )


class TestH4rm3lFramer(unittest.TestCase):
    def test_preset_program_frames_goal(self):
        framer = build_jailbreak_framer(
            {
                "enabled": True,
                "technique": "h4rm3l",
                "program": "refusal_suppression",
            },
            LOGGER,
        )
        framed, metadata = framer.apply("do the bad thing")
        self.assertIn("do the bad thing", framed)
        self.assertNotEqual(framed, "do the bad thing")
        self.assertEqual(metadata["technique"], "h4rm3l")
        self.assertEqual(metadata["program"], "refusal_suppression")

    def test_llm_assisted_program_raises(self):
        with self.assertRaises(ValueError):
            build_jailbreak_framer(
                {
                    "enabled": True,
                    "technique": "h4rm3l",
                    "program": "pap_logical_appeal",
                },
                LOGGER,
            )


class TestFlipattackFramer(unittest.TestCase):
    def test_default_mode_reverses_sentence(self):
        framer = build_jailbreak_framer(
            {"enabled": True, "technique": "flipattack"}, LOGGER
        )
        framed, metadata = framer.apply("do the bad thing")
        self.assertEqual(framed, "do the bad thing"[::-1])
        self.assertEqual(metadata["technique"], "flipattack")
        self.assertEqual(metadata["flip_mode"], "FCS")

    def test_word_order_mode(self):
        framer = build_jailbreak_framer(
            {"enabled": True, "technique": "flipattack", "flip_mode": "FWO"},
            LOGGER,
        )
        framed, _ = framer.apply("do the bad thing")
        self.assertEqual(framed, "thing bad the do")

    def test_char_in_word_mode(self):
        framer = build_jailbreak_framer(
            {"enabled": True, "technique": "flipattack", "flip_mode": "FCW"},
            LOGGER,
        )
        framed, _ = framer.apply("do bad")
        self.assertEqual(framed, "od dab")

    def test_variant_index_rotates_modes(self):
        framer = build_jailbreak_framer(
            {
                "enabled": True,
                "technique": "flipattack",
                "flip_modes": ["FWO", "FCS"],
            },
            LOGGER,
        )
        first, meta_first = framer.apply("do the bad thing", 0)
        second, meta_second = framer.apply("do the bad thing", 1)
        self.assertNotEqual(first, second)
        self.assertEqual(meta_first["flip_mode"], "FWO")
        self.assertEqual(meta_second["flip_mode"], "FCS")

    def test_unsupported_mode_raises(self):
        with self.assertRaises(ValueError):
            build_jailbreak_framer(
                {"enabled": True, "technique": "flipattack", "flip_mode": "NOPE"},
                LOGGER,
            )


if __name__ == "__main__":
    unittest.main()
