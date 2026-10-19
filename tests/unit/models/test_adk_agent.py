# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for the Google ADK backend.

ADK is routed through LiteLLM via a custom provider, so ``ADKModel`` does not
make the HTTP calls itself — its custom handler does. These tests exercise both
layers: handler-level (HTTP transport) and model-level (end-to-end via the
public ``complete``).
"""

import logging
import unittest
from unittest.mock import MagicMock, patch

import httpx

from hackagent.core.contracts import AgentType, ModelSpec
from hackagent.models.completions import adk as adk_module
from hackagent.models.completions.adk import (
    ADKConfigurationError,
    ADKInteractionError,
    ADKModel,
    _extract_final_text,
    _get_adk_custom_llm_class,
)
from hackagent.models.completions.cli import last_user_text as _last_user_text

logging.disable(logging.CRITICAL)


def _make_httpx_http_status_error(
    status_code: int, text: str = "boom"
) -> httpx.HTTPStatusError:
    """Build an HTTPStatusError with attached request/response for tests."""
    request = httpx.Request("POST", "http://fake-adk.com")
    response = httpx.Response(status_code, text=text, request=request)
    return httpx.HTTPStatusError(
        f"HTTP Error: {status_code}", request=request, response=response
    )


def _spec(**config):
    name = config.pop("name", "test_app")
    endpoint = config.pop("endpoint", "http://fake-adk.com")
    timeout = config.pop("timeout", None)
    return ModelSpec(
        identifier=name,
        agent_type=AgentType.GOOGLE_ADK,
        endpoint=endpoint,
        timeout=timeout,
        extra=dict(config),
    )


def _model(**config):
    return ADKModel(_spec(**config))


def _make_handler(**overrides):
    """Construct an _ADKCustomLLM with sensible defaults for tests."""
    handler_cls = _get_adk_custom_llm_class()
    defaults = dict(
        endpoint="http://fake-adk.com",
        app_name="test_app",
        user_id="test_user",
        default_session_id="sess-default",
        fresh_session_per_request=False,
        timeout=30,
        log=logging.getLogger("test"),
    )
    defaults.update(overrides)
    return handler_cls(**defaults)


class TestADKModuleLayout(unittest.TestCase):
    """ADK lives at ``models/completions/adk.py``."""

    def test_helpers_are_module_level(self):
        self.assertIs(_extract_final_text, adk_module._extract_final_text)
        self.assertIs(ADKModel, adk_module.ADKModel)


class TestADKHelpers(unittest.TestCase):
    def test_last_user_text_returns_last_user_string(self):
        messages = [
            {"role": "system", "content": "be terse"},
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "ack"},
            {"role": "user", "content": "second"},
        ]
        self.assertEqual(_last_user_text(messages), "second")

    def test_last_user_text_handles_content_parts(self):
        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": "from-parts"}],
            }
        ]
        self.assertEqual(_last_user_text(messages), "from-parts")

    def test_last_user_text_returns_none_when_no_user_message(self):
        self.assertIsNone(_last_user_text([{"role": "system", "content": "x"}]))

    def test_extract_final_text_returns_latest_text(self):
        events = [
            {"content": {"parts": [{"text": "first"}]}},
            {"content": {"parts": [{"text": "final"}]}},
        ]
        self.assertEqual(_extract_final_text(events), "final")

    def test_extract_final_text_handles_escalation(self):
        events = [
            {"content": {"parts": [{"text": "x"}]}},
            {"actions": {"escalate": True}, "error_message": "boom"},
        ]
        self.assertEqual(_extract_final_text(events), "Agent escalated: boom")

    def test_extract_final_text_returns_none_when_no_text(self):
        self.assertIsNone(_extract_final_text([{"content": {}}]))


class TestADKCustomLLMTransport(unittest.TestCase):
    @patch("httpx.post")
    def test_create_session_success(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200, raise_for_status=MagicMock()
        )
        handler = _make_handler()
        handler._create_session(session_id="abc")
        kwargs = mock_post.call_args.kwargs
        self.assertEqual(kwargs["timeout"], 30)
        self.assertEqual(kwargs["json"], {})

    @patch("httpx.post")
    def test_create_session_with_initial_state(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200, raise_for_status=MagicMock()
        )
        handler = _make_handler()
        handler._create_session(session_id="abc", initial_state={"k": "v"})
        self.assertEqual(mock_post.call_args.kwargs["json"], {"k": "v"})

    @patch("httpx.post")
    def test_create_session_409_is_idempotent(self, mock_post):
        mock_resp = MagicMock(status_code=409)
        mock_resp.raise_for_status.side_effect = _make_httpx_http_status_error(409)
        mock_post.return_value = mock_resp
        handler = _make_handler()
        handler._create_session(session_id="abc")  # no raise

    @patch("httpx.post")
    def test_create_session_400_with_already_exists_text_is_idempotent(self, mock_post):
        mock_resp = MagicMock(
            status_code=400,
            text="Session already exists for this user and app.",
        )
        mock_resp.raise_for_status.side_effect = _make_httpx_http_status_error(
            400, text="Session already exists for this user and app."
        )
        mock_post.return_value = mock_resp
        handler = _make_handler()
        handler._create_session(session_id="abc")

    @patch("httpx.post")
    def test_create_session_other_http_error_raises(self, mock_post):
        mock_resp = MagicMock(status_code=500, text="boom")
        mock_resp.raise_for_status.side_effect = _make_httpx_http_status_error(500)
        mock_post.return_value = mock_resp
        handler = _make_handler()
        with self.assertRaises(ADKInteractionError):
            handler._create_session(session_id="abc")

    @patch("httpx.post")
    def test_create_session_connection_error_raises(self, mock_post):
        mock_post.side_effect = httpx.RequestError(
            "nope", request=httpx.Request("POST", "http://fake-adk.com")
        )
        handler = _make_handler()
        with self.assertRaises(ADKInteractionError):
            handler._create_session(session_id="abc")

    @patch("httpx.post")
    def test_run_returns_final_text_from_events(self, mock_post):
        events = [
            {"content": {"parts": [{"text": "ignored"}]}},
            {"content": {"parts": [{"text": "the answer"}]}},
        ]
        mock_resp = MagicMock(status_code=200, headers={"X": "1"})
        mock_resp.text = "[]"
        mock_resp.json.return_value = events
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp
        handler = _make_handler()
        result = handler._run(prompt_text="hi", session_id="s1")
        self.assertEqual(result["final_text"], "the answer")
        self.assertEqual(result["events"], events)
        self.assertEqual(result["status_code"], 200)


class TestADKModelInit(unittest.TestCase):
    def test_init_success(self):
        model = _model(
            name="my_app",
            endpoint="http://fake-adk.com/",
            user_id="alice",
            timeout=60,
        )
        self.assertEqual(model.endpoint, "http://fake-adk.com")
        self.assertEqual(model.name, "my_app")
        self.assertEqual(model.user_id, "alice")
        self.assertEqual(model.timeout, 60)
        # The model routes through LiteLLM under a per-instance provider.
        self.assertTrue(
            model.litellm_model.startswith("hackagent_adk_")
            and model.litellm_model.endswith("/my_app")
        )

    def test_init_default_timeout(self):
        model = _model(name="a", endpoint="http://x", user_id="u")
        self.assertEqual(model.timeout, 120)

    def test_init_user_id_defaults(self):
        model = _model(name="a", endpoint="http://x")
        self.assertEqual(model.user_id, "hackagent")

    def test_init_missing_name(self):
        with self.assertRaises(ADKConfigurationError):
            ADKModel(
                ModelSpec(
                    identifier="",
                    agent_type=AgentType.GOOGLE_ADK,
                    endpoint="http://x",
                    extra={"user_id": "u"},
                )
            )

    def test_init_missing_endpoint(self):
        with self.assertRaises(ADKConfigurationError):
            ADKModel(
                ModelSpec(
                    identifier="a",
                    agent_type=AgentType.GOOGLE_ADK,
                    extra={"user_id": "u"},
                )
            )

    def test_init_registers_custom_provider(self):
        import litellm

        model = _model(name="app", endpoint="http://fake-adk.com", user_id="u")
        providers = [entry["provider"] for entry in litellm.custom_provider_map]
        self.assertIn(f"hackagent_adk_{model.id}", providers)

    def test_registered_in_native_model_map(self):
        from hackagent.models.build import _native_model_classes

        self.assertIs(_native_model_classes()[AgentType.GOOGLE_ADK], ADKModel)


class TestADKModelComplete(unittest.TestCase):
    def setUp(self):
        self.model = _model(
            name="test_app",
            endpoint="http://fake-adk.com",
            user_id="u",
            fresh_session_per_request=False,
        )

    @patch("httpx.post")
    def test_complete_success_routes_through_adk(self, mock_post):
        # First call creates the session; second call is /run.
        session_resp = MagicMock(status_code=200, raise_for_status=MagicMock())
        run_events = [{"content": {"parts": [{"text": "agent reply"}]}}]
        run_resp = MagicMock(status_code=200, headers={"X": "1"}, text="[]")
        run_resp.json.return_value = run_events
        run_resp.raise_for_status = MagicMock()
        mock_post.side_effect = [session_resp, run_resp]

        response = self.model.complete([{"role": "user", "content": "hello"}])

        self.assertEqual(response.text, "agent reply")
        self.assertIsNone(response.error)
        self.assertEqual(response.metadata.get("adk_events_list"), run_events)
        self.assertEqual(response.metadata.get("adk_session_id"), self.model.session_id)

    @patch("httpx.post")
    def test_complete_uses_explicit_session_id(self, mock_post):
        session_resp = MagicMock(status_code=200, raise_for_status=MagicMock())
        run_resp = MagicMock(status_code=200, headers={}, text="[]")
        run_resp.json.return_value = [{"content": {"parts": [{"text": "ok"}]}}]
        run_resp.raise_for_status = MagicMock()
        mock_post.side_effect = [session_resp, run_resp]

        response = self.model.complete(
            [{"role": "user", "content": "hi"}], session_id="explicit-123"
        )
        self.assertIsNone(response.error)
        self.assertEqual(response.metadata.get("adk_session_id"), "explicit-123")
        # Session-create POST should target the explicit id.
        session_call_url = mock_post.call_args_list[0][0][0]
        self.assertIn("/sessions/explicit-123", session_call_url)

    @patch("httpx.post")
    def test_complete_run_http_error_returns_error(self, mock_post):
        session_resp = MagicMock(status_code=200, raise_for_status=MagicMock())
        run_resp = MagicMock(status_code=500, text="boom", headers={})
        run_resp.raise_for_status.side_effect = _make_httpx_http_status_error(500)
        mock_post.side_effect = [session_resp, run_resp]
        response = self.model.complete([{"role": "user", "content": "hi"}])
        self.assertIsNotNone(response.error)
        self.assertIn("HTTP Error: 500", response.error.message)


if __name__ == "__main__":
    unittest.main()
