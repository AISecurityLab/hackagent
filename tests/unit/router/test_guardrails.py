# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import json
import unittest
import uuid
from unittest.mock import MagicMock, patch

from hackagent.attacks.shared.guardrail import (
    BaseGuardrail,
    GuardrailResult,
    LLMGuardrail,
    create_guardrail_from_config,
)
from hackagent.router.router import AgentRouter, _extract_prompt_text
from hackagent.router.types import AgentTypeEnum


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_backend(org_id=None, user_id="test_user"):
    backend = MagicMock()
    ctx = MagicMock()
    ctx.org_id = org_id or uuid.uuid4()
    ctx.user_id = user_id
    backend.get_context.return_value = ctx
    backend.get_api_key.return_value = None
    return backend


def _make_router_with_guardrails(before_guardrail=None, after_guardrail=None):
    """Build an AgentRouter with mocked internals, attaching guardrails."""
    with patch("hackagent.router.router.ADKAgent", autospec=True) as MockADK:
        MockADK.__name__ = "ADKAgent"
        with patch(
            "hackagent.router.router.AGENT_TYPE_TO_ADAPTER_MAP",
            {AgentTypeEnum.GOOGLE_ADK: MockADK},
        ):
            backend = _make_backend()
            agent_id = uuid.uuid4()
            backend.create_or_update_agent.return_value = MagicMock(
                id=agent_id,
                name="TestAgent",
                agent_type="GOOGLE_ADK",
                endpoint="http://fake.com/",
                metadata={},
                organization=uuid.uuid4(),
                owner="local",
            )
            router = AgentRouter(
                backend=backend,
                name="TestAgent",
                agent_type=AgentTypeEnum.GOOGLE_ADK,
                endpoint="http://fake.com/",
            )
    router.before_guardrail = before_guardrail
    router.after_guardrail = after_guardrail
    return router, str(agent_id)


# ---------------------------------------------------------------------------
# Tests: _extract_prompt_text
# ---------------------------------------------------------------------------


class TestExtractPromptText(unittest.TestCase):
    def test_returns_last_user_message(self):
        data = {
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"},
                {"role": "user", "content": "How are you?"},
            ]
        }
        self.assertEqual(_extract_prompt_text(data), "How are you?")

    def test_fallback_concatenation_when_no_user_role(self):
        data = {
            "messages": [
                {"role": "system", "content": "sys"},
                {"role": "assistant", "content": "resp"},
            ]
        }
        result = _extract_prompt_text(data)
        self.assertIn("sys", result)
        self.assertIn("resp", result)

    def test_fallback_to_prompt_key(self):
        data = {"prompt": "Tell me a joke"}
        self.assertEqual(_extract_prompt_text(data), "Tell me a joke")

    def test_returns_empty_string_when_no_data(self):
        self.assertEqual(_extract_prompt_text({}), "")

    def test_returns_empty_string_when_messages_empty(self):
        self.assertEqual(_extract_prompt_text({"messages": []}), "")

    def test_handles_none_content(self):
        data = {"messages": [{"role": "user", "content": None}]}
        self.assertEqual(_extract_prompt_text(data), "")


# ---------------------------------------------------------------------------
# Tests: GuardrailResult
# ---------------------------------------------------------------------------


class TestGuardrailResult(unittest.TestCase):
    def test_basic_construction(self):
        r = GuardrailResult(is_safe=True, explanation="All good")
        self.assertTrue(r.is_safe)
        self.assertEqual(r.explanation, "All good")
        self.assertEqual(r.categories, [])
        self.assertIsNone(r.raw_response)

    def test_unsafe_with_categories(self):
        r = GuardrailResult(
            is_safe=False,
            explanation="Harmful",
            categories=["violence", "hate"],
            raw_response='{"safe": false}',
        )
        self.assertFalse(r.is_safe)
        self.assertEqual(r.categories, ["violence", "hate"])

    def test_frozen_immutability(self):
        r = GuardrailResult(is_safe=True, explanation="ok")
        with self.assertRaises(Exception):
            r.is_safe = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Tests: LLMGuardrail._parse (static method)
# ---------------------------------------------------------------------------


class TestLLMGuardrailParse(unittest.TestCase):
    def test_valid_safe_json(self):
        raw = json.dumps({"safe": True, "categories": [], "reasoning": "Looks fine"})
        result = LLMGuardrail._parse(raw)
        self.assertTrue(result.is_safe)
        self.assertEqual(result.explanation, "Looks fine")
        self.assertEqual(result.categories, [])

    def test_valid_unsafe_json(self):
        raw = json.dumps(
            {
                "safe": False,
                "categories": ["violence"],
                "reasoning": "Contains threats",
            }
        )
        result = LLMGuardrail._parse(raw)
        self.assertFalse(result.is_safe)
        self.assertEqual(result.categories, ["violence"])
        self.assertEqual(result.explanation, "Contains threats")

    def test_empty_string_fails_open(self):
        result = LLMGuardrail._parse("")
        self.assertTrue(result.is_safe)

    def test_whitespace_only_fails_open(self):
        result = LLMGuardrail._parse("   \n  ")
        self.assertTrue(result.is_safe)

    def test_invalid_json_with_unsafe_keyword(self):
        raw = "This content is UNSAFE and should be blocked"
        result = LLMGuardrail._parse(raw)
        self.assertFalse(result.is_safe)

    def test_invalid_json_with_safe_false_keyword(self):
        raw = 'Blah blah "safe": false blah'
        result = LLMGuardrail._parse(raw)
        self.assertFalse(result.is_safe)

    def test_invalid_json_without_unsafe_keyword_fails_open(self):
        raw = "I cannot evaluate this text properly"
        result = LLMGuardrail._parse(raw)
        self.assertTrue(result.is_safe)

    def test_json_missing_fields_defaults(self):
        raw = json.dumps({"safe": True})
        result = LLMGuardrail._parse(raw)
        self.assertTrue(result.is_safe)
        self.assertEqual(result.explanation, "")
        self.assertEqual(result.categories, [])


# ---------------------------------------------------------------------------
# Tests: LLMGuardrail.check
# ---------------------------------------------------------------------------


class TestLLMGuardrailCheck(unittest.TestCase):
    @patch("hackagent.attacks.shared.guardrail.create_router")
    def _make_guardrail(self, mock_create_router, router_response=None):
        mock_router = MagicMock()
        mock_create_router.return_value = (mock_router, "guardrail-key")
        config = {
            "identifier": "test-model",
            "endpoint": "http://fake.com/v1",
            "agent_type": "OPENAI_SDK",
        }
        guardrail = LLMGuardrail(config=config, backend=MagicMock())
        if router_response is not None:
            mock_router.route_request.return_value = router_response
        return guardrail, mock_router

    def test_empty_text_fails_open(self):
        guardrail, _ = self._make_guardrail()
        result = guardrail.check("")
        self.assertTrue(result.is_safe)

    def test_whitespace_text_fails_open(self):
        guardrail, _ = self._make_guardrail()
        result = guardrail.check("   ")
        self.assertTrue(result.is_safe)

    def test_safe_response(self):
        safe_json = json.dumps({"safe": True, "categories": [], "reasoning": "ok"})
        guardrail, mock_router = self._make_guardrail(
            router_response={"processed_response": safe_json, "error_message": None}
        )
        result = guardrail.check("Hello world")
        self.assertTrue(result.is_safe)
        mock_router.route_request.assert_called_once()

    def test_unsafe_response(self):
        unsafe_json = json.dumps(
            {"safe": False, "categories": ["harm"], "reasoning": "Bad content"}
        )
        guardrail, _ = self._make_guardrail(
            router_response={
                "processed_response": unsafe_json,
                "error_message": None,
            }
        )
        result = guardrail.check("Harmful request")
        self.assertFalse(result.is_safe)
        self.assertEqual(result.categories, ["harm"])

    def test_router_error_fails_open(self):
        guardrail, _ = self._make_guardrail(
            router_response={
                "processed_response": None,
                "error_message": "Connection timeout",
            }
        )
        result = guardrail.check("Some text")
        self.assertTrue(result.is_safe)
        self.assertIn("Connection timeout", result.explanation)


# ---------------------------------------------------------------------------
# Tests: create_guardrail_from_config
# ---------------------------------------------------------------------------


class TestCreateGuardrailFromConfig(unittest.TestCase):
    @patch("hackagent.attacks.shared.guardrail.create_router")
    def test_returns_llm_guardrail(self, mock_create_router):
        mock_create_router.return_value = (MagicMock(), "key")
        config = {"identifier": "model", "endpoint": "http://e.com/v1"}
        guardrail = create_guardrail_from_config(config=config, backend=MagicMock())
        self.assertIsInstance(guardrail, LLMGuardrail)
        self.assertIsInstance(guardrail, BaseGuardrail)


# ---------------------------------------------------------------------------
# Tests: Before guardrail in AgentRouter.route_request
# ---------------------------------------------------------------------------


class TestBeforeGuardrailRouting(unittest.TestCase):
    def test_no_guardrail_passes_through(self):
        router, reg_key = _make_router_with_guardrails(before_guardrail=None)
        expected = {"processed_response": "Hello!", "error_message": None}
        router._agent_registry[reg_key].handle_request.return_value = expected

        result = router.route_request(
            registration_key=reg_key,
            request_data={"messages": [{"role": "user", "content": "Hi"}]},
        )
        self.assertEqual(result["processed_response"], "Hello!")

    def test_safe_prompt_passes_through(self):
        mock_guardrail = MagicMock(spec=BaseGuardrail)
        mock_guardrail.check.return_value = GuardrailResult(
            is_safe=True, explanation="ok"
        )
        router, reg_key = _make_router_with_guardrails(before_guardrail=mock_guardrail)
        expected = {"processed_response": "Answer", "error_message": None}
        router._agent_registry[reg_key].handle_request.return_value = expected

        result = router.route_request(
            registration_key=reg_key,
            request_data={"messages": [{"role": "user", "content": "Legit question"}]},
        )
        mock_guardrail.check.assert_called_once_with("Legit question")
        self.assertEqual(result["processed_response"], "Answer")

    def test_unsafe_prompt_is_blocked(self):
        mock_guardrail = MagicMock(spec=BaseGuardrail)
        mock_guardrail.check.return_value = GuardrailResult(
            is_safe=False, explanation="Violent content", categories=["violence"]
        )
        router, reg_key = _make_router_with_guardrails(before_guardrail=mock_guardrail)

        result = router.route_request(
            registration_key=reg_key,
            request_data={"messages": [{"role": "user", "content": "Bad stuff"}]},
        )
        self.assertIsNone(result["processed_response"])
        self.assertEqual(
            result["agent_specific_data"]["guardrail"], "before_guardrail_blocked"
        )
        self.assertEqual(result["agent_specific_data"]["side"], "before")
        self.assertEqual(result["agent_specific_data"]["categories"], ["violence"])
        self.assertEqual(result["agent_specific_data"]["reasoning"], "Violent content")
        # Adapter should NOT be called
        router._agent_registry[reg_key].handle_request.assert_not_called()

    def test_empty_prompt_skips_guardrail(self):
        mock_guardrail = MagicMock(spec=BaseGuardrail)
        router, reg_key = _make_router_with_guardrails(before_guardrail=mock_guardrail)
        expected = {"processed_response": "Answer", "error_message": None}
        router._agent_registry[reg_key].handle_request.return_value = expected

        result = router.route_request(
            registration_key=reg_key,
            request_data={"messages": [{"role": "user", "content": ""}]},
        )
        mock_guardrail.check.assert_not_called()
        self.assertEqual(result["processed_response"], "Answer")


# ---------------------------------------------------------------------------
# Tests: After guardrail in AgentRouter.route_request
# ---------------------------------------------------------------------------


class TestAfterGuardrailRouting(unittest.TestCase):
    def test_no_guardrail_passes_through(self):
        router, reg_key = _make_router_with_guardrails(after_guardrail=None)
        expected = {"processed_response": "Hello!", "error_message": None}
        router._agent_registry[reg_key].handle_request.return_value = expected

        result = router.route_request(
            registration_key=reg_key,
            request_data={"messages": [{"role": "user", "content": "Hi"}]},
        )
        self.assertEqual(result["processed_response"], "Hello!")

    def test_safe_response_passes_through(self):
        mock_guardrail = MagicMock(spec=BaseGuardrail)
        mock_guardrail.check.return_value = GuardrailResult(
            is_safe=True, explanation="ok"
        )
        router, reg_key = _make_router_with_guardrails(after_guardrail=mock_guardrail)
        expected = {
            "processed_response": "Safe answer",
            "generated_text": None,
            "error_message": None,
        }
        router._agent_registry[reg_key].handle_request.return_value = expected

        result = router.route_request(
            registration_key=reg_key,
            request_data={"messages": [{"role": "user", "content": "Question"}]},
        )
        mock_guardrail.check.assert_called_once_with("Safe answer")
        self.assertEqual(result["processed_response"], "Safe answer")

    def test_unsafe_response_is_censored(self):
        mock_guardrail = MagicMock(spec=BaseGuardrail)
        mock_guardrail.check.return_value = GuardrailResult(
            is_safe=False,
            explanation="Contains PII",
            categories=["privacy"],
        )
        router, reg_key = _make_router_with_guardrails(after_guardrail=mock_guardrail)
        expected = {
            "processed_response": "Here is your SSN: 123-45-6789",
            "generated_text": None,
            "error_message": None,
        }
        router._agent_registry[reg_key].handle_request.return_value = expected

        result = router.route_request(
            registration_key=reg_key,
            request_data={"messages": [{"role": "user", "content": "My SSN?"}]},
        )
        self.assertIsNone(result["processed_response"])
        self.assertEqual(
            result["agent_specific_data"]["guardrail"], "after_guardrail_censored"
        )
        self.assertEqual(result["agent_specific_data"]["side"], "after")
        self.assertEqual(result["agent_specific_data"]["categories"], ["privacy"])
        self.assertEqual(result["agent_specific_data"]["reasoning"], "Contains PII")

    def test_empty_response_skips_guardrail(self):
        mock_guardrail = MagicMock(spec=BaseGuardrail)
        router, reg_key = _make_router_with_guardrails(after_guardrail=mock_guardrail)
        expected = {
            "processed_response": "",
            "generated_text": None,
            "error_message": None,
        }
        router._agent_registry[reg_key].handle_request.return_value = expected

        router.route_request(
            registration_key=reg_key,
            request_data={"messages": [{"role": "user", "content": "Hi"}]},
        )
        mock_guardrail.check.assert_not_called()

    def test_falls_back_to_generated_text(self):
        mock_guardrail = MagicMock(spec=BaseGuardrail)
        mock_guardrail.check.return_value = GuardrailResult(
            is_safe=True, explanation="ok"
        )
        router, reg_key = _make_router_with_guardrails(after_guardrail=mock_guardrail)
        expected = {
            "processed_response": None,
            "generated_text": "Fallback text",
            "error_message": None,
        }
        router._agent_registry[reg_key].handle_request.return_value = expected

        router.route_request(
            registration_key=reg_key,
            request_data={"messages": [{"role": "user", "content": "Hi"}]},
        )
        mock_guardrail.check.assert_called_once_with("Fallback text")


if __name__ == "__main__":
    unittest.main()
