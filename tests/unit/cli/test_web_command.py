# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the `hackagent web` CLI command."""

import unittest
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from hackagent.cli.commands.web import (
    _free_port,
    _is_hackagent_process,
    _listener_pids,
    web,
)


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


class TestFreePort(unittest.TestCase):
    """Test the safe port-reclaim behaviour of the web command."""

    def test_free_port_returns_true_when_port_is_free(self):
        with patch("hackagent.cli.commands.web._port_in_use", return_value=False):
            self.assertTrue(_free_port("127.0.0.1", 7860))

    def test_free_port_kills_only_hackagent_listener(self):
        with (
            patch(
                "hackagent.cli.commands.web._port_in_use", return_value=True
            ),
            patch(
                "hackagent.cli.commands.web._listener_pids",
                return_value=["4242"],
            ),
            patch(
                "hackagent.cli.commands.web._is_hackagent_process",
                return_value=True,
            ),
            patch("hackagent.cli.commands.web.os.kill") as mock_kill,
            patch("hackagent.cli.commands.web.time.sleep"),
        ):
            self.assertTrue(_free_port("127.0.0.1", 7860))
            mock_kill.assert_called_once_with(4242, 15)

    def test_free_port_refuses_foreign_listener(self):
        with (
            patch(
                "hackagent.cli.commands.web._port_in_use", return_value=True
            ),
            patch(
                "hackagent.cli.commands.web._listener_pids",
                return_value=["4242"],
            ),
            patch(
                "hackagent.cli.commands.web._is_hackagent_process",
                return_value=False,
            ),
            patch("hackagent.cli.commands.web.os.kill") as mock_kill,
        ):
            self.assertFalse(_free_port("127.0.0.1", 7860))
            mock_kill.assert_not_called()

    def test_free_port_refuses_when_listener_unknown(self):
        with (
            patch(
                "hackagent.cli.commands.web._port_in_use", return_value=True
            ),
            patch(
                "hackagent.cli.commands.web._listener_pids", return_value=[]
            ),
            patch("hackagent.cli.commands.web.os.kill") as mock_kill,
        ):
            self.assertFalse(_free_port("127.0.0.1", 7860))
            mock_kill.assert_not_called()

    def test_is_hackagent_process_matches_command_line(self):
        with patch(
            "hackagent.cli.commands.web.subprocess.check_output",
            return_value="hackagent web --port 7860\n",
        ):
            self.assertTrue(_is_hackagent_process("4242"))

    def test_listener_pids_ignores_non_numeric_lines(self):
        with patch(
            "hackagent.cli.commands.web.subprocess.check_output",
            return_value="4242\nnot-a-pid\n7777\n",
        ):
            self.assertEqual(_listener_pids(7860), ["4242", "7777"])

    def test_web_local_mode_foreign_port_exits_without_running(self):
        runner = CliRunner()
        config = MagicMock()
        config.api_key = None
        config.base_url = "https://api.hackagent.dev"

        app = MagicMock()
        with (
            patch(
                "hackagent.server.storage.local.LocalBackend",
                return_value=_DummyLocalBackend(),
            ),
            patch(
                "hackagent.server.dashboard.create_app", return_value=app
            ),
            patch("hackagent.cli.commands.web._free_port", return_value=False),
        ):
            result = runner.invoke(
                web, ["--no-browser"], obj={"config": config}
            )

        self.assertNotEqual(result.exit_code, 0)
        app.run.assert_not_called()
        self.assertIn("already in use", result.output)


if __name__ == "__main__":
    unittest.main()
