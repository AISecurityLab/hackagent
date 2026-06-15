# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for ``AgentRouter._dispatch_via_litellm`` — Phase C of #379.

The dispatch path lives on the router itself and is exercised end-to-end
by going through ``AgentRouter.route_request``. These tests mock the
backend so the router can be initialised with a real adapter instance,
then patch ``litellm.completion`` to control the response.
"""

import logging
import unittest
import uuid
from unittest.mock import MagicMock, patch

from hackagent.router.router import AgentRouter
from hackagent.router.types import AgentTypeEnum
from hackagent.server.storage.base import OrganizationContext

logging.disable(logging.CRITICAL)


def _make_litellm_response(content: str = "ok") -> MagicMock:
    response = MagicMock()
    choice = MagicMock()
    message = MagicMock()
    message.content = content
    message.tool_calls = None
    message.reasoning_content = None
    message.reasoning = None
    message.provider_specific_fields = None
    choice.message = message
    choice.finish_reason = "stop"
    response.choices = [choice]
    response.usage = MagicMock(model_dump=MagicMock(return_value={"total_tokens": 7}))
    response.model = "openai/gpt-4"
    return response


def _make_context(org_id=None, user_id="test_user"):
    ctx = MagicMock(spec=OrganizationContext)
    ctx.org_id = org_id or uuid.uuid4()
    ctx.user_id = user_id
    return ctx


def _make_agent_rec(*, agent_id, name, agent_type_str, endpoint, metadata=None):
    rec = MagicMock()
    rec.id = agent_id
    rec.name = name
    rec.agent_type = agent_type_str
    rec.endpoint = endpoint
    rec.metadata = metadata or {}
    rec.organization = uuid.uuid4()
    rec.owner = "local"
    return rec


def _make_backend(*, agent_id, name, agent_type_str, endpoint, metadata=None):
    backend = MagicMock()
    backend.get_context.return_value = _make_context()
    backend.get_api_key.return_value = None
    backend.create_or_update_agent.return_value = _make_agent_rec(
        agent_id=agent_id,
        name=name,
        agent_type_str=agent_type_str,
        endpoint=endpoint,
        metadata=metadata,
    )
    return backend


class TestDispatchViaLiteLLM(unittest.TestCase):
    """Verify the chat path goes through litellm.completion directly."""

    def _make_router_for_openai(self):
        agent_id = uuid.uuid4()
        backend = _make_backend(
            agent_id=agent_id,
            name="gpt-4-router-test",
            agent_type_str=AgentTypeEnum.OPENAI_SDK.value,
            endpoint="",
            metadata={"name": "gpt-4"},
        )
        router = AgentRouter(
            backend=backend,
            name="gpt-4-router-test",
            agent_type=AgentTypeEnum.OPENAI_SDK,
            endpoint="",
            metadata={"name": "gpt-4"},
            adapter_operational_config={"name": "gpt-4"},
        )
        return router, str(agent_id)

    @patch("litellm.completion")
    def test_chat_request_goes_through_litellm_completion(self, mock_completion):
        """OPENAI_SDK request lands at litellm.completion via the router."""
        mock_completion.return_value = _make_litellm_response("hi there")
        router, reg_key = self._make_router_for_openai()

        # Patch the adapter's handle_request so we can verify it's NOT called.
        adapter = router.get_agent_instance(reg_key)
        adapter.handle_request = MagicMock(name="should_not_be_called")

        response = router.route_request(reg_key, {"prompt": "hi"})

        self.assertEqual(response["status_code"], 200)
        self.assertEqual(response["generated_text"], "hi there")
        self.assertEqual(response["adapter_type"], "OpenAIAgent")
        mock_completion.assert_called_once()
        adapter.handle_request.assert_not_called()
        kwargs = mock_completion.call_args.kwargs
        self.assertEqual(kwargs["model"], "openai/gpt-4")
        self.assertEqual(kwargs["messages"], [{"role": "user", "content": "hi"}])

    @patch("litellm.completion")
    def test_missing_prompt_returns_400_envelope_from_router(self, mock_completion):
        router, reg_key = self._make_router_for_openai()
        response = router.route_request(reg_key, {"temperature": 0.5})
        self.assertEqual(response["status_code"], 400)
        self.assertIn(
            "Request data must include either 'messages' or 'prompt'",
            response["error_message"],
        )
        mock_completion.assert_not_called()

    @patch("litellm.completion")
    def test_litellm_exception_becomes_500_envelope(self, mock_completion):
        mock_completion.side_effect = RuntimeError("boom")
        router, reg_key = self._make_router_for_openai()
        response = router.route_request(reg_key, {"prompt": "hi"})
        self.assertEqual(response["status_code"], 500)
        self.assertIn("boom", response["error_message"])
        self.assertEqual(response["adapter_type"], "OpenAIAgent")

    @patch("litellm.completion")
    def test_thinking_translation_applied_through_router(self, mock_completion):
        """Per-request ``thinking`` flag is translated by the ProviderConfig."""
        mock_completion.return_value = _make_litellm_response("ok")
        agent_id = uuid.uuid4()
        backend = _make_backend(
            agent_id=agent_id,
            name="o1-mini",
            agent_type_str=AgentTypeEnum.OPENAI_SDK.value,
            endpoint="",
            metadata={"name": "o1-mini"},
        )
        router = AgentRouter(
            backend=backend,
            name="o1-mini",
            agent_type=AgentTypeEnum.OPENAI_SDK,
            endpoint="",
            metadata={"name": "o1-mini"},
            adapter_operational_config={"name": "o1-mini"},
        )
        reg_key = str(agent_id)
        router.route_request(reg_key, {"prompt": "hi", "thinking": True})
        kwargs = mock_completion.call_args.kwargs
        self.assertEqual(kwargs.get("reasoning_effort"), "medium")

    @patch("litellm.completion")
    def test_dispatch_attaches_hackagent_metadata_namespace(self, mock_completion):
        """Phase F.2 — identifiers live under ``metadata['hackagent']``."""
        mock_completion.return_value = _make_litellm_response("ok")
        router, reg_key = self._make_router_for_openai()
        router.route_request(reg_key, {"prompt": "hi"})
        metadata = mock_completion.call_args.kwargs.get("metadata")
        self.assertIsInstance(metadata, dict)
        ha = metadata.get("hackagent")
        self.assertIsInstance(ha, dict)
        self.assertEqual(ha["id"], reg_key)
        self.assertEqual(ha["adapter_type"], "OpenAIAgent")
        # No flat hackagent_* keys at the top level any more.
        self.assertNotIn("hackagent_agent_id", metadata)

    @patch("litellm.completion")
    def test_caller_metadata_outside_hackagent_namespace_preserved(
        self, mock_completion
    ):
        mock_completion.return_value = _make_litellm_response("ok")
        router, reg_key = self._make_router_for_openai()
        router.route_request(
            reg_key,
            {"prompt": "hi", "metadata": {"trace_id": "xyz", "user_id": "alice"}},
        )
        metadata = mock_completion.call_args.kwargs.get("metadata")
        # Caller's keys are preserved verbatim.
        self.assertEqual(metadata["trace_id"], "xyz")
        self.assertEqual(metadata["user_id"], "alice")
        # Router still sets its own namespace.
        self.assertEqual(metadata["hackagent"]["id"], reg_key)

    @patch("litellm.completion")
    def test_caller_hackagent_namespace_wins_on_collision(self, mock_completion):
        """Caller-supplied ``metadata['hackagent']`` keys override the router's."""
        mock_completion.return_value = _make_litellm_response("ok")
        router, reg_key = self._make_router_for_openai()
        router.route_request(
            reg_key,
            {
                "prompt": "hi",
                "metadata": {"hackagent": {"id": "override", "custom": "x"}},
            },
        )
        metadata = mock_completion.call_args.kwargs.get("metadata")
        ha = metadata["hackagent"]
        self.assertEqual(ha["id"], "override")
        # Custom keys inside the namespace pass through.
        self.assertEqual(ha["custom"], "x")
        # adapter_type still set by the router since the caller didn't override it.
        self.assertEqual(ha["adapter_type"], "OpenAIAgent")

    def test_unknown_registration_key_returns_404_envelope(self):
        router, _ = self._make_router_for_openai()
        response = router.route_request("nonexistent-key", {"prompt": "hi"})
        # Phase F.1 unified the field name; legacy ``raw_response_status``
        # stays as a back-compat alias.
        self.assertEqual(response["status_code"], 404)
        self.assertEqual(response["raw_response_status"], 404)
        self.assertIn("Agent not found", response["error_message"])

    @patch("litellm.completion")
    def test_response_cost_and_call_id_surface_in_envelope(self, mock_completion):
        """Phase F.1 — LiteLLM's response_cost / call_id show up in the envelope."""
        response = _make_litellm_response("ok")
        response._hidden_params = {
            "response_cost": 0.000123,
            "litellm_call_id": "call-abc",
        }
        mock_completion.return_value = response

        router, reg_key = self._make_router_for_openai()
        env = router.route_request(reg_key, {"prompt": "hi"})

        self.assertEqual(env["status_code"], 200)
        agent_data = env["agent_specific_data"]
        self.assertAlmostEqual(agent_data["response_cost"], 0.000123)
        self.assertEqual(agent_data["litellm_call_id"], "call-abc")

    @patch("litellm.completion")
    def test_response_cost_absent_when_not_in_hidden_params(self, mock_completion):
        """No ``response_cost`` from LiteLLM → envelope omits the field."""
        response = _make_litellm_response("ok")
        # Don't set _hidden_params; cost should just be missing.
        if hasattr(response, "_hidden_params"):
            del response._hidden_params
        mock_completion.return_value = response

        router, reg_key = self._make_router_for_openai()
        env = router.route_request(reg_key, {"prompt": "hi"})
        self.assertNotIn("response_cost", env["agent_specific_data"])


class TestDispatchADKBypassesLiteLLM(unittest.TestCase):
    """Verify ADK requests still flow through the adapter's handle_request."""

    def test_adk_uses_adapter_handle_request_not_litellm(self):
        agent_id = uuid.uuid4()
        backend = _make_backend(
            agent_id=agent_id,
            name="my_app",
            agent_type_str=AgentTypeEnum.GOOGLE_ADK.value,
            endpoint="http://fake-adk.com",
            metadata={"name": "my_app"},
        )
        router = AgentRouter(
            backend=backend,
            name="my_app",
            agent_type=AgentTypeEnum.GOOGLE_ADK,
            endpoint="http://fake-adk.com",
            metadata={"name": "my_app"},
            adapter_operational_config={
                "name": "my_app",
                "endpoint": "http://fake-adk.com",
                "user_id": "alice",
            },
        )
        reg_key = str(agent_id)
        adapter = router.get_agent_instance(reg_key)
        adapter.handle_request = MagicMock(
            return_value={
                "status_code": 200,
                "generated_text": "adk reply",
                "adapter_type": "ADKAgent",
                "agent_id": reg_key,
                "error_message": None,
            }
        )

        with patch("litellm.completion") as mock_completion:
            response = router.route_request(reg_key, {"prompt": "hi"})

        self.assertEqual(response["generated_text"], "adk reply")
        adapter.handle_request.assert_called_once()
        mock_completion.assert_not_called()


if __name__ == "__main__":
    unittest.main()
