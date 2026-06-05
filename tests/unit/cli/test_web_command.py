# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the `hackagent web` CLI command."""

import unittest
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from hackagent.cli.commands.web import web


class _DummyLocalBackend:
    pass


class TestWebCommand(unittest.TestCase):
    """Test backend selection and command execution for web CLI."""

    def _free_port_socket(self):
        mock_socket = MagicMock()
        mock_socket.__enter__.return_value.connect_ex.return_value = 1
        return mock_socket

    def test_web_remote_mode_opens_cloud_dashboard(self):
        runner = CliRunner()
        config = MagicMock()
        config.api_key = "test-key"
        config.base_url = "https://api.hackagent.dev"
        with (
            patch("webbrowser.open", return_value=True) as mock_open,
            patch("hackagent.server.dashboard.create_app") as mock_create_app,
        ):
            result = runner.invoke(web, [], obj={"config": config})

        self.assertEqual(result.exit_code, 0)
        mock_open.assert_called_once_with("https://app.hackagent.dev")
        mock_create_app.assert_not_called()

    def test_web_remote_mode_no_browser_does_not_open_browser(self):
        runner = CliRunner()
        config = MagicMock()
        config.api_key = "test-key"
        config.base_url = "https://api.hackagent.dev"

        with (
            patch("webbrowser.open") as mock_open,
            patch("hackagent.server.dashboard.create_app") as mock_create_app,
        ):
            result = runner.invoke(web, ["--no-browser"], obj={"config": config})

        self.assertEqual(result.exit_code, 0)
        mock_open.assert_not_called()
        mock_create_app.assert_not_called()

    def test_web_local_mode_uses_local_dashboard(self):
        runner = CliRunner()
        config = MagicMock()
        config.api_key = None
        config.base_url = "https://api.hackagent.dev"

        local_backend = _DummyLocalBackend()
        app = MagicMock()

        with (
            patch(
                "hackagent.server.storage.local.LocalBackend",
                return_value=local_backend,
            ) as mock_local_cls,
            patch(
                "hackagent.server.dashboard.create_app", return_value=app
            ) as mock_create_app,
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
