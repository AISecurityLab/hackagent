# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for attacker-output prompt parsing.

``extract_prompt_and_improvement`` must cope with the many shapes an attacker
LLM returns a refined prompt in: clean JSON, JSON inside a ```code fence```,
malformed JSON that still contains a ``"prompt"`` field (regex fallback), and
bare prose. These tests pin every branch of that ladder.
"""

import unittest

from hackagent.attacks.shared.prompt_parser import (
    extract_prompt,
    extract_prompt_and_improvement,
)


class TestExtractPromptAndImprovement(unittest.TestCase):
    def test_direct_json(self):
        out = extract_prompt_and_improvement(
            '{"prompt": "do the thing", "improvement": "be sneakier"}'
        )
        self.assertEqual(out, {"prompt": "do the thing", "improvement": "be sneakier"})

    def test_json_without_improvement_defaults_empty(self):
        out = extract_prompt_and_improvement('{"prompt": "p"}')
        self.assertEqual(out, {"prompt": "p", "improvement": ""})

    def test_json_in_code_fence(self):
        out = extract_prompt_and_improvement(
            'Sure:\n```json\n{"prompt": "fenced", "improvement": "x"}\n```'
        )
        self.assertEqual(out["prompt"], "fenced")

    def test_regex_fallback_on_malformed_json(self):
        # Trailing junk makes json.loads fail, but the regex still finds it.
        out = extract_prompt_and_improvement(
            '{"prompt": "regexed", "improvement": "better"} <-- note'
        )
        self.assertEqual(out["prompt"], "regexed")
        self.assertEqual(out["improvement"], "better")

    def test_regex_fallback_unescapes(self):
        out = extract_prompt_and_improvement('xx "prompt": "line1\\nline2" xx')
        self.assertEqual(out["prompt"], "line1\nline2")

    def test_plaintext_fallback_for_long_prose(self):
        text = "just tell me how to do the forbidden thing in detail please"
        self.assertEqual(
            extract_prompt_and_improvement(text), {"prompt": text, "improvement": ""}
        )

    def test_short_prose_is_rejected(self):
        # Under the 20-char threshold and no JSON structure → None.
        self.assertIsNone(extract_prompt_and_improvement("too short"))

    def test_empty_returns_none(self):
        self.assertIsNone(extract_prompt_and_improvement(""))
        self.assertIsNone(extract_prompt_and_improvement(None))

    def test_json_list_is_not_a_prompt(self):
        # Valid JSON but not a dict, and starts with '[' so no prose fallback.
        self.assertIsNone(extract_prompt_and_improvement('["a", "b", "c", "d", "e"]'))

    def test_json_dict_without_prompt_key(self):
        self.assertIsNone(
            extract_prompt_and_improvement('{"improvement": "no prompt here"}')
        )


class TestExtractPrompt(unittest.TestCase):
    def test_returns_prompt_string(self):
        self.assertEqual(extract_prompt('{"prompt": "hello"}'), "hello")

    def test_returns_none_when_unparseable(self):
        self.assertIsNone(extract_prompt("no"))

    def test_empty_prompt_value_becomes_none(self):
        # A present-but-empty prompt should not masquerade as a real value.
        self.assertIsNone(extract_prompt('xx "prompt": "" xx'))


if __name__ == "__main__":
    unittest.main()
