# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for cached attack-prompt translation."""

import unittest

from hackagent.attacks.shared.translation import (
    clear_cache,
    detect_language,
    localize_text,
)


class TestPromptTranslation(unittest.TestCase):
    def setUp(self):
        clear_cache()

    def test_english_goal_is_passthrough(self):
        calls = []

        def complete(p):
            calls.append(p)
            return "English" if p.startswith("Identify") else "should-not-be-used"

        text = "You are a red teaming assistant."
        self.assertEqual(localize_text(text, "how do I cure a wound", complete), text)
        # Only the detection call ran; no translation.
        self.assertEqual(len([c for c in calls if "TEXT:" in c]), 0)

    def test_non_english_goal_translates_and_caches(self):
        translate_calls = []

        def complete(p):
            if p.startswith("Identify"):
                return "Italian.\n"
            translate_calls.append(p)
            return "Sei un assistente di red teaming."

        text = "You are a red teaming assistant."
        out1 = localize_text(text, "mi spiegami come curarmi", complete)
        self.assertEqual(out1, "Sei un assistente di red teaming.")

        # Same text + same language (different goal) → translate cache hit.
        out2 = localize_text(text, "un'altra frase italiana", complete)
        self.assertEqual(out2, out1)
        self.assertEqual(len(translate_calls), 1)  # translated only once

    def test_translation_failure_falls_back_to_original(self):
        def complete(p):
            if p.startswith("Identify"):
                return "Italian"
            raise RuntimeError("model down")

        text = "original english prompt"
        self.assertEqual(localize_text(text, "ciao mondo", complete), text)

    def test_empty_translation_falls_back_to_original(self):
        def complete(p):
            return "Italian" if p.startswith("Identify") else "   "

        text = "original"
        self.assertEqual(localize_text(text, "ciao", complete), text)

    def test_detect_language_caches_per_goal(self):
        calls = []

        def complete(p):
            calls.append(p)
            return "French"

        self.assertEqual(detect_language("bonjour le monde", complete), "French")
        self.assertEqual(detect_language("bonjour le monde", complete), "French")
        self.assertEqual(len(calls), 1)  # cached

    def test_detect_language_handles_preamble(self):
        # Robust to a non-compliant reply that wraps the name in a sentence.
        self.assertEqual(
            detect_language("hola", lambda p: "The language is Spanish."), "Spanish"
        )
        clear_cache()
        self.assertEqual(detect_language("ciao", lambda p: "Italian."), "Italian")


if __name__ == "__main__":
    unittest.main()
