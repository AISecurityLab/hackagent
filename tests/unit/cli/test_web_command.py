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
    """Stand-in for LocalBackend that records whether it was closed."""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class TestWebCommand(unittest.TestCase):
    """Test mode selection and command execution for the web CLI."""

    def _free_port_socket(self):
        mock_socket = MagicMock()
        mock_socket.__enter__.return_value.connect_ex.return_value = 1
        return mock_socket

    def test_web_remote_mode_proxies_with_api_key(self):
        runner = CliRunner()
        config = MagicMock()
        config.api_key = "test-key"
        config.base_url = "https://api.hackagent.dev"
        app = MagicMock()

        with (
            patch("hackagent.server.webui.create_app", return_value=app) as mock_create,
            patch("hackagent.storage.local.LocalBackend") as mock_local_cls,
            patch("socket.socket", return_value=self._free_port_socket()),
        ):
            result = runner.invoke(web, ["--no-browser"], obj={"config": config})

        self.assertEqual(result.exit_code, 0)
        # Remote mode must not touch the local database at all.
        mock_local_cls.assert_not_called()
        mock_create.assert_called_once_with(
            backend=None,
            api_key="test-key",
            base_url="https://api.hackagent.dev",
        )
        app.run.assert_called_once_with(host="127.0.0.1", port=7860, threaded=True)

    def test_web_local_mode_serves_from_local_backend(self):
        runner = CliRunner()
        config = MagicMock()
        config.api_key = None
        config.base_url = "https://api.hackagent.dev"

        local_backend = _DummyLocalBackend()
        app = MagicMock()

        with (
            patch(
                "hackagent.storage.local.LocalBackend",
                return_value=local_backend,
            ) as mock_local_cls,
            patch("hackagent.server.webui.create_app", return_value=app) as mock_create,
            patch("socket.socket", return_value=self._free_port_socket()),
        ):
            result = runner.invoke(
                web,
                ["--db-path", "/tmp/test-dashboard.db", "--no-browser"],
                obj={"config": config},
            )

        self.assertEqual(result.exit_code, 0)
        mock_local_cls.assert_called_once_with(db_path="/tmp/test-dashboard.db")
        mock_create.assert_called_once_with(
            backend=local_backend,
            api_key=None,
            base_url="https://api.hackagent.dev",
        )
        app.run.assert_called_once_with(host="127.0.0.1", port=7860, threaded=True)
        self.assertTrue(local_backend.closed)

    def test_web_local_flag_overrides_configured_api_key(self):
        runner = CliRunner()
        config = MagicMock()
        config.api_key = "test-key"
        config.base_url = "https://api.hackagent.dev"

        local_backend = _DummyLocalBackend()
        app = MagicMock()

        with (
            patch(
                "hackagent.storage.local.LocalBackend",
                return_value=local_backend,
            ),
            patch("hackagent.server.webui.create_app", return_value=app) as mock_create,
            patch("socket.socket", return_value=self._free_port_socket()),
        ):
            result = runner.invoke(
                web, ["--local", "--no-browser"], obj={"config": config}
            )

        self.assertEqual(result.exit_code, 0)
        self.assertIsNone(mock_create.call_args.kwargs["api_key"])

    def test_web_without_bundle_exits_with_guidance(self):
        runner = CliRunner()
        config = MagicMock()
        config.api_key = None
        config.base_url = "https://api.hackagent.dev"

        from hackagent.server.webui import MissingBundleError

        with (
            patch(
                "hackagent.storage.local.LocalBackend",
                return_value=_DummyLocalBackend(),
            ),
            patch(
                "hackagent.server.webui.create_app",
                side_effect=MissingBundleError(),
            ),
        ):
            result = runner.invoke(web, ["--no-browser"], obj={"config": config})

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("No web UI bundle", result.output)

    def test_web_opens_browser_once_the_server_is_up(self):
        runner = CliRunner()
        config = MagicMock()
        config.api_key = "test-key"
        config.base_url = "https://api.hackagent.dev"

        with (
            patch("hackagent.server.webui.create_app", return_value=MagicMock()),
            patch("socket.socket", return_value=self._free_port_socket()),
            patch(
                "hackagent.cli.commands.web._open_browser_when_up"
            ) as mock_open_browser,
        ):
            result = runner.invoke(web, [], obj={"config": config})

        self.assertEqual(result.exit_code, 0)
        mock_open_browser.assert_called_once_with(
            "http://127.0.0.1:7860", "127.0.0.1", 7860
        )


class TestFreePort(unittest.TestCase):
    """Test the safe port-reclaim behaviour of the web command."""

    def test_free_port_returns_true_when_port_is_free(self):
        with patch("hackagent.cli.commands.web._port_in_use", return_value=False):
            self.assertTrue(_free_port("127.0.0.1", 7860))

    def test_free_port_kills_only_hackagent_listener(self):
        with (
            patch("hackagent.cli.commands.web._port_in_use", return_value=True),
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
            patch("hackagent.cli.commands.web._port_in_use", return_value=True),
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
            patch("hackagent.cli.commands.web._port_in_use", return_value=True),
            patch("hackagent.cli.commands.web._listener_pids", return_value=[]),
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
                "hackagent.storage.local.LocalBackend",
                return_value=_DummyLocalBackend(),
            ),
            patch("hackagent.server.webui.create_app", return_value=app),
            patch("hackagent.cli.commands.web._free_port", return_value=False),
        ):
            result = runner.invoke(web, ["--no-browser"], obj={"config": config})

        self.assertNotEqual(result.exit_code, 0)
        app.run.assert_not_called()
        self.assertIn("already in use", result.output)


if __name__ == "__main__":
    unittest.main()
