# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import json
import unittest
from unittest.mock import MagicMock

from hackagent.models.guardrail import (
    GuardedModel,
    GuardrailResult,
    GuardrailSpec,
    LLMGuardrail,
    parse_verdict,
)
from tests.fakes import FakeLLM


def _guardrail(is_safe: bool, explanation: str = "ok", categories=None):
    guardrail = MagicMock()
    guardrail.check.return_value = GuardrailResult(
        is_safe=is_safe, explanation=explanation, categories=categories or []
    )
    return guardrail


def _chat(text: str):
    return [{"role": "user", "content": text}]


# ---------------------------------------------------------------------------
# GuardrailResult and parse_verdict
# ---------------------------------------------------------------------------


class TestGuardrailResult(unittest.TestCase):
    def test_basic_construction(self):
        r = GuardrailResult(is_safe=True, explanation="All good")
        self.assertTrue(r.is_safe)
        self.assertEqual(r.categories, [])
        self.assertIsNone(r.raw_response)

    def test_frozen_immutability(self):
        r = GuardrailResult(is_safe=True, explanation="ok")
        with self.assertRaises(Exception):
            r.is_safe = False  # type: ignore[misc]


class TestParseVerdict(unittest.TestCase):
    def test_valid_safe_json(self):
        raw = json.dumps({"safe": True, "categories": [], "reasoning": "Looks fine"})
        result = parse_verdict(raw)
        self.assertTrue(result.is_safe)
        self.assertEqual(result.explanation, "Looks fine")

    def test_valid_unsafe_json(self):
        raw = json.dumps(
            {"safe": False, "categories": ["violence"], "reasoning": "Threats"}
        )
        result = parse_verdict(raw)
        self.assertFalse(result.is_safe)
        self.assertEqual(result.categories, ["violence"])
        self.assertEqual(result.explanation, "Threats")

    def test_empty_or_whitespace_fails_open(self):
        self.assertTrue(parse_verdict("").is_safe)
        self.assertTrue(parse_verdict("   \n  ").is_safe)

    def test_invalid_json_with_unsafe_keyword(self):
        self.assertFalse(parse_verdict("This content is UNSAFE").is_safe)
        self.assertFalse(parse_verdict('Blah "safe": false blah').is_safe)

    def test_invalid_json_without_unsafe_keyword_fails_open(self):
        self.assertTrue(parse_verdict("I cannot evaluate this").is_safe)

    def test_json_missing_fields_defaults(self):
        result = parse_verdict(json.dumps({"safe": True}))
        self.assertTrue(result.is_safe)
        self.assertEqual(result.explanation, "")
        self.assertEqual(result.categories, [])


# ---------------------------------------------------------------------------
# LLMGuardrail (the classifier that drives a model)
# ---------------------------------------------------------------------------


class TestLLMGuardrailCheck(unittest.TestCase):
    def test_empty_text_fails_open_without_calling_the_model(self):
        llm = FakeLLM()
        guardrail = LLMGuardrail(llm)
        self.assertTrue(guardrail.check("").is_safe)
        self.assertTrue(guardrail.check("   ").is_safe)
        self.assertEqual(llm.requests, [])

    def test_sends_system_prompt_and_text(self):
        llm = FakeLLM([json.dumps({"safe": True})])
        LLMGuardrail(llm, system_prompt="classify").check("Hello world")

        request = llm.requests[0]
        self.assertEqual(
            request["messages"],
            [
                {"role": "system", "content": "classify"},
                {"role": "user", "content": "Hello world"},
            ],
        )
        self.assertEqual(request["max_tokens"], 256)
        self.assertEqual(request["temperature"], 0)

    def test_unsafe_response(self):
        llm = FakeLLM(
            [json.dumps({"safe": False, "categories": ["harm"], "reasoning": "Bad"})]
        )
        result = LLMGuardrail(llm).check("Harmful request")
        self.assertFalse(result.is_safe)
        self.assertEqual(result.categories, ["harm"])

    def test_model_error_fails_open(self):
        llm = FakeLLM(
            [{"processed_response": None, "error_message": "Connection timeout"}]
        )
        result = LLMGuardrail(llm).check("Some text")
        self.assertTrue(result.is_safe)
        self.assertIn("Connection timeout", result.explanation)


class TestGuardrailSpec(unittest.TestCase):
    def test_system_prompt_is_a_field(self):
        spec = GuardrailSpec(identifier="m", system_prompt="custom")
        self.assertEqual(spec.system_prompt, "custom")


# ---------------------------------------------------------------------------
# GuardedModel (guardrails wrapped around a native Model)
# ---------------------------------------------------------------------------


class TestGuardedModelBefore(unittest.TestCase):
    def test_no_guardrail_passes_through(self):
        response = GuardedModel(FakeLLM(["Hello!"])).complete(_chat("Hi"))
        self.assertEqual(response.text, "Hello!")
        self.assertIsNone(response.guardrail)

    def test_safe_prompt_reaches_the_model(self):
        before = _guardrail(True)
        inner = FakeLLM(["Answer"])
        response = GuardedModel(inner, before=before).complete(_chat("Legit question"))
        before.check.assert_called_once_with("Legit question")
        self.assertEqual(response.text, "Answer")

    def test_unsafe_prompt_is_blocked_before_the_model(self):
        before = _guardrail(False, "Violent content", ["violence"])
        inner = FakeLLM(["Answer"])

        response = GuardedModel(inner, before=before).complete(_chat("Bad stuff"))

        self.assertEqual(response.text, "")
        self.assertIsNotNone(response.guardrail)
        self.assertEqual(response.guardrail.side, "before")
        self.assertEqual(response.guardrail.categories, ["violence"])
        self.assertEqual(response.guardrail.reasoning, "Violent content")
        self.assertEqual(inner.requests, [])  # the model was never called

    def test_empty_prompt_skips_guardrail(self):
        before = _guardrail(False)
        response = GuardedModel(FakeLLM(["Answer"]), before=before).complete(_chat(""))
        before.check.assert_not_called()
        self.assertEqual(response.text, "Answer")


class TestGuardedModelAfter(unittest.TestCase):
    def test_safe_response_passes_through(self):
        after = _guardrail(True)
        response = GuardedModel(FakeLLM(["Safe answer"]), after=after).complete(
            _chat("Q")
        )
        after.check.assert_called_once_with("Safe answer")
        self.assertEqual(response.text, "Safe answer")

    def test_unsafe_response_is_censored(self):
        after = _guardrail(False, "Contains PII", ["privacy"])
        response = GuardedModel(FakeLLM(["SSN: 123-45-6789"]), after=after).complete(
            _chat("Q")
        )
        self.assertEqual(response.text, "")
        self.assertEqual(response.guardrail.side, "after")
        self.assertEqual(response.guardrail.categories, ["privacy"])

    def test_async_applies_both_guardrails(self):
        after = _guardrail(False, "leak")
        response = asyncio.run(
            GuardedModel(
                FakeLLM(["secret"]), before=_guardrail(True), after=after
            ).acomplete(_chat("Q"))
        )
        self.assertEqual(response.guardrail.side, "after")


if __name__ == "__main__":
    unittest.main()
