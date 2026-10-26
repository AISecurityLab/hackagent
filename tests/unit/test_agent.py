# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the facade session and a bound target."""

import unittest
from unittest.mock import patch

from hackagent import HackAgent, Settings
from tests.fakes import in_memory_store


def _settings(**kwargs):
    kwargs.setdefault("backend", "remote" if kwargs.get("api_key") else "local")
    kwargs.setdefault("db_path", ":memory:")
    kwargs.setdefault("env", {})
    kwargs.setdefault("config_path", "/nonexistent/hackagent/config.json")
    return Settings.resolve(**kwargs)


def _target(**kwargs):
    store = kwargs.pop("store", None) or in_memory_store()
    endpoint = kwargs.pop("endpoint", "http://localhost:8000")
    agent_type = kwargs.pop("agent_type", "openai-sdk")
    name = kwargs.pop("name", "test-agent")
    session = HackAgent(_settings(), backend=store)
    return session.target(endpoint, agent_type, name=name, **kwargs), store


class TestHackAgentSession(unittest.TestCase):
    def test_remote_session_defaults_to_a_120_second_timeout(self):
        with patch("hackagent.storage.remote.RemoteBackend.connect") as connect:
            HackAgent(
                _settings(api_key="test-key", base_url="https://api.hackagent.dev")
            )
        connect.assert_called_once()
        self.assertEqual(connect.call_args.kwargs["timeout"], 120.0)
        self.assertEqual(connect.call_args.args[1], "test-key")

    def test_custom_base_url_and_timeout_are_forwarded(self):
        with patch("hackagent.storage.remote.RemoteBackend.connect") as connect:
            HackAgent(
                _settings(api_key="test-key", base_url="https://custom.api.com"),
                timeout=15.0,
            )
        self.assertEqual(connect.call_args.args[0], "https://custom.api.com")
        self.assertEqual(connect.call_args.kwargs["timeout"], 15.0)

    def test_explicit_none_timeout_disables_it(self):
        with patch("hackagent.storage.remote.RemoteBackend.connect") as connect:
            HackAgent(_settings(api_key="test-key"), timeout=None)
        self.assertIsNone(connect.call_args.kwargs["timeout"])
