# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import json
import unittest
from unittest.mock import MagicMock

from hackagent.models.envelope import prompt_text, to_completion
from hackagent.models.guardrail import (
    Guarded,
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
    return {"messages": [{"role": "user", "content": text}]}


# ---------------------------------------------------------------------------
# prompt_text
# ---------------------------------------------------------------------------


class TestPromptText(unittest.TestCase):
    def test_returns_last_user_message(self):
        data = {
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"},
                {"role": "user", "content": "How are you?"},
            ]
        }
        self.assertEqual(prompt_text(data), "How are you?")

    def test_fallback_concatenation_when_no_user_role(self):
        data = {
            "messages": [
                {"role": "system", "content": "sys"},
                {"role": "assistant", "content": "resp"},
            ]
        }
        result = prompt_text(data)
        self.assertIn("sys", result)
        self.assertIn("resp", result)

    def test_fallback_to_prompt_key(self):
        self.assertEqual(prompt_text({"prompt": "Tell me a joke"}), "Tell me a joke")

    def test_returns_empty_string_when_no_data(self):
        self.assertEqual(prompt_text({}), "")
        self.assertEqual(prompt_text({"messages": []}), "")

    def test_handles_none_content(self):
        data = {"messages": [{"role": "user", "content": None}]}
        self.assertEqual(prompt_text(data), "")


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
# LLMGuardrail
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
# Guarded
# ---------------------------------------------------------------------------


class TestGuardedBefore(unittest.TestCase):
    def test_no_guardrail_passes_through(self):
        inner = FakeLLM(["Hello!"])
        result = Guarded(inner).send(_chat("Hi"))
        self.assertEqual(result["processed_response"], "Hello!")

    def test_safe_prompt_passes_through(self):
        before = _guardrail(True)
        inner = FakeLLM(["Answer"])
        result = Guarded(inner, before=before).send(_chat("Legit question"))
        before.check.assert_called_once_with("Legit question")
        self.assertEqual(result["processed_response"], "Answer")

    def test_unsafe_prompt_is_blocked_before_the_model(self):
        before = _guardrail(False, "Violent content", ["violence"])
        inner = FakeLLM()

        result = Guarded(inner, before=before).send(_chat("Bad stuff"))

        self.assertIsNone(result["processed_response"])
        data = result["agent_specific_data"]
        self.assertEqual(data["guardrail"], "before_guardrail_blocked")
        self.assertEqual(data["side"], "before")
        self.assertEqual(data["categories"], ["violence"])
        self.assertEqual(data["reasoning"], "Violent content")
        self.assertEqual(inner.requests, [])

    def test_empty_prompt_skips_guardrail(self):
        before = _guardrail(False)
        result = Guarded(FakeLLM(["Answer"]), before=before).send(_chat(""))
        before.check.assert_not_called()
        self.assertEqual(result["processed_response"], "Answer")


class TestGuardedAfter(unittest.TestCase):
    def test_safe_response_passes_through(self):
        after = _guardrail(True)
        result = Guarded(FakeLLM(["Safe answer"]), after=after).send(_chat("Q"))
        after.check.assert_called_once_with("Safe answer")
        self.assertEqual(result["processed_response"], "Safe answer")

    def test_unsafe_response_is_censored(self):
        after = _guardrail(False, "Contains PII", ["privacy"])
        result = Guarded(FakeLLM(["SSN: 123-45-6789"]), after=after).send(_chat("Q"))
        self.assertIsNone(result["processed_response"])
        data = result["agent_specific_data"]
        self.assertEqual(data["guardrail"], "after_guardrail_censored")
        self.assertEqual(data["side"], "after")
        self.assertEqual(data["categories"], ["privacy"])

    def test_empty_response_skips_guardrail(self):
        after = _guardrail(False)
        Guarded(FakeLLM([""]), after=after).send(_chat("Hi"))
        after.check.assert_not_called()

    def test_falls_back_to_generated_text(self):
        after = _guardrail(True)
        inner = FakeLLM(
            [{"processed_response": None, "generated_text": "Fallback text"}]
        )
        Guarded(inner, after=after).send(_chat("Hi"))
        after.check.assert_called_once_with("Fallback text")


class TestGuardedAsLLM(unittest.TestCase):
    def test_complete_reports_a_blocked_prompt(self):
        before = _guardrail(False, "nope", ["harm"])
        completion = Guarded(FakeLLM(), before=before).complete("Bad stuff")
        self.assertFalse(completion.ok)
        self.assertEqual(completion.guardrail.side, "before")
        self.assertEqual(completion.guardrail.categories, ["harm"])
        self.assertIsNone(completion.text)

    def test_async_send_applies_both_guardrails(self):
        after = _guardrail(False, "leak")
        result = asyncio.run(
            Guarded(FakeLLM(["secret"]), before=_guardrail(True), after=after).asend(
                _chat("Q")
            )
        )
        self.assertEqual(
            result["agent_specific_data"]["guardrail"], "after_guardrail_censored"
        )

    def test_with_params_keeps_the_guardrails(self):
        before = _guardrail(False)
        guarded = Guarded(FakeLLM(), before=before).with_params(max_tokens=5)
        self.assertIs(guarded.before, before)
        result = guarded.send(_chat("x"))
        self.assertEqual(
            to_completion(result).guardrail.side,
            "before",
        )


if __name__ == "__main__":
    unittest.main()
