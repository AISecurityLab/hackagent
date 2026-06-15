# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for ``hackagent/router/tracking_logger.py``."""

import datetime as _dt
import logging
import unittest
from unittest.mock import MagicMock, patch

from hackagent.router import tracking_logger

logging.disable(logging.CRITICAL)


def _hackagent_kwargs(**overrides):
    """Build a kwargs dict shaped the way LiteLLM passes one to a callback."""
    base = {
        "model": "openai/gpt-4",
        "messages": [{"role": "user", "content": "hello"}],
        "litellm_call_id": "call-1",
        "response_cost": 0.0001,
        "litellm_params": {
            "metadata": {
                "hackagent": {
                    "id": "agent-123",
                    "adapter_type": "OpenAIAgent",
                },
            },
        },
    }
    base.update(overrides)
    return base


def _model_response(content: str = "ok"):
    response = MagicMock()
    message = MagicMock()
    message.content = content
    message.reasoning_content = None
    message.reasoning = None
    choice = MagicMock()
    choice.message = message
    response.choices = [choice]
    return response


class TestEnsureRegistered(unittest.TestCase):
    def setUp(self):
        tracking_logger._reset_for_tests()
        import litellm

        # Snapshot callbacks so we can restore them.
        self._saved_callbacks = list(getattr(litellm, "callbacks", None) or [])
        litellm.callbacks = list(self._saved_callbacks)
        self._litellm = litellm

    def tearDown(self):
        self._litellm.callbacks = self._saved_callbacks
        tracking_logger._reset_for_tests()

    def test_idempotent_registration(self):
        self.assertTrue(tracking_logger.ensure_registered())
        first_callbacks = list(self._litellm.callbacks)
        self.assertTrue(tracking_logger.ensure_registered())
        self.assertEqual(list(self._litellm.callbacks), first_callbacks)

    def test_logger_instance_exposed(self):
        tracking_logger.ensure_registered()
        self.assertIsNotNone(tracking_logger.get_instance())


class TestCallbackFilteringByMetadata(unittest.TestCase):
    """Calls without the HackAgent sentinel metadata are ignored."""

    def setUp(self):
        tracking_logger._reset_for_tests()
        tracking_logger.ensure_registered()
        self.logger = tracking_logger.get_instance()

    def tearDown(self):
        tracking_logger._reset_for_tests()

    @patch.object(tracking_logger._TRACKING_LOGGER, "info")
    def test_pre_call_with_no_metadata_is_skipped(self, mock_info):
        self.logger.log_pre_api_call(
            "openai/gpt-4",
            [{"role": "user", "content": "hi"}],
            {"litellm_params": {}},  # no metadata
        )
        mock_info.assert_not_called()

    @patch.object(tracking_logger._TRACKING_LOGGER, "info")
    def test_pre_call_with_hackagent_metadata_is_logged(self, mock_info):
        self.logger.log_pre_api_call(
            "openai/gpt-4",
            [{"role": "user", "content": "hi"}],
            _hackagent_kwargs(),
        )
        mock_info.assert_called_once()
        extra = mock_info.call_args.kwargs["extra"]
        self.assertEqual(extra["hackagent_agent_id"], "agent-123")
        self.assertEqual(extra["hackagent_adapter_type"], "OpenAIAgent")

    @patch.object(tracking_logger._TRACKING_LOGGER, "info")
    def test_success_logs_cost_call_id_and_preview(self, mock_info):
        start = _dt.datetime(2026, 1, 1, 0, 0, 0)
        end = _dt.datetime(2026, 1, 1, 0, 0, 1)
        self.logger.log_success_event(
            _hackagent_kwargs(), _model_response("hi"), start, end
        )
        mock_info.assert_called_once()
        extra = mock_info.call_args.kwargs["extra"]
        self.assertEqual(extra["litellm_call_id"], "call-1")
        self.assertEqual(extra["response_cost"], 0.0001)
        self.assertEqual(extra["response_preview"], "hi")
        self.assertAlmostEqual(extra["duration_ms"], 1000.0, places=1)

    @patch.object(tracking_logger._TRACKING_LOGGER, "warning")
    def test_failure_logs_exception_repr(self, mock_warning):
        start = _dt.datetime(2026, 1, 1, 0, 0, 0)
        end = _dt.datetime(2026, 1, 1, 0, 0, 1)
        kwargs = _hackagent_kwargs(exception=RuntimeError("boom"))
        self.logger.log_failure_event(kwargs, None, start, end)
        mock_warning.assert_called_once()
        extra = mock_warning.call_args.kwargs["extra"]
        self.assertIn("boom", extra["exception_repr"])


if __name__ == "__main__":
    unittest.main()
