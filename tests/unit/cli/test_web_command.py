# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the `hackagent web` CLI command."""

import unittest
from unittest.mock import MagicMock, patch

import httpx
from click.testing import CliRunner

from hackagent.cli.commands.web import web


class _DummyRemoteBackend:
    def __init__(self):
        self.get_context_calls = 0

    def get_context(self):
        self.get_context_calls += 1
        return {"ok": True}


class _DummyLocalBackend:
    pass


class TestWebCommand(unittest.TestCase):
    """Test backend selection and command execution for web CLI."""

    def _free_port_socket(self):
        mock_socket = MagicMock()
        mock_socket.__enter__.return_value.connect_ex.return_value = 1
        return mock_socket

    def test_web_uses_remote_backend_when_preflight_succeeds(self):
        runner = CliRunner()
        config = MagicMock()
        config.api_key = "test-key"
        config.base_url = "https://api.hackagent.dev"

        remote_backend = _DummyRemoteBackend()
        app = MagicMock()

        with (
            patch("hackagent.server.client.AuthenticatedClient") as mock_auth_client,
            patch(
                "hackagent.server.storage.remote.RemoteBackend",
                return_value=remote_backend,
            ) as mock_remote_cls,
            patch("hackagent.server.storage.local.LocalBackend") as mock_local_cls,
            patch("hackagent.server.dashboard.create_app", return_value=app) as mock_create_app,
            patch("socket.socket", return_value=self._free_port_socket()),
        ):
            result = runner.invoke(
                web,
                ["--host", "127.0.0.1", "--port", "7878"],
                obj={"config": config},
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(remote_backend.get_context_calls, 1)
        mock_remote_cls.assert_called_once()
        mock_local_cls.assert_not_called()
        mock_create_app.assert_called_once_with(backend=remote_backend)
        app.run.assert_called_once_with(host="127.0.0.1", port=7878, show=True)

        _, auth_kwargs = mock_auth_client.call_args
        self.assertEqual(auth_kwargs["base_url"], "https://api.hackagent.dev")
        self.assertEqual(auth_kwargs["token"], "test-key")
        self.assertIsInstance(auth_kwargs["timeout"], httpx.Timeout)

    def test_web_falls_back_to_local_backend_when_remote_preflight_fails(self):
        runner = CliRunner()
        config = MagicMock()
        config.api_key = "test-key"
        config.base_url = "https://api.hackagent.dev"

        remote_backend = _DummyRemoteBackend()

        def _raise_preflight_error():
            raise RuntimeError("remote unavailable")

        remote_backend.get_context = _raise_preflight_error
        local_backend = _DummyLocalBackend()
        app = MagicMock()

        with (
            patch("hackagent.server.client.AuthenticatedClient"),
            patch(
                "hackagent.server.storage.remote.RemoteBackend",
                return_value=remote_backend,
            ),
            patch(
                "hackagent.server.storage.local.LocalBackend",
                return_value=local_backend,
            ) as mock_local_cls,
            patch("hackagent.server.dashboard.create_app", return_value=app) as mock_create_app,
            patch("socket.socket", return_value=self._free_port_socket()),
        ):
            result = runner.invoke(
                web,
                ["--db-path", "/tmp/test-dashboard.db", "--no-browser"],
                obj={"config": config},
            )

        self.assertEqual(result.exit_code, 0)
        mock_local_cls.assert_called_once_with(db_path="/tmp/test-dashboard.db")
        mock_create_app.assert_called_once_with(backend=local_backend)
        app.run.assert_called_once_with(host="127.0.0.1", port=7860, show=False)


if __name__ == "__main__":
    unittest.main()
