# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the default TUI launch / welcome screen bootstrap."""

import sys
import unittest
from unittest.mock import MagicMock, patch

from hackagent.cli import bootstrap

try:
    import termios
except ImportError:  # pragma: no cover - Windows / non-POSIX
    termios = None


class TestPatchTextualTerminalQueries(unittest.TestCase):
    @unittest.skipIf(
        termios is None,
        "Textual linux drivers import termios, which is unavailable on Windows",
    )
    def test_both_linux_drivers_are_neutralised(self):
        from textual.drivers.linux_driver import LinuxDriver
        from textual.drivers.linux_inline_driver import LinuxInlineDriver

        for driver in (LinuxDriver, LinuxInlineDriver):
            # The attribute may or may not exist on the installed textual
            # version, so restore whichever state we found.
            if "_query_in_band_window_resize" in vars(driver):
                self.addCleanup(
                    setattr,
                    driver,
                    "_query_in_band_window_resize",
                    vars(driver)["_query_in_band_window_resize"],
                )
            else:
                self.addCleanup(delattr, driver, "_query_in_band_window_resize")

        bootstrap._patch_textual_terminal_queries()

        # The patched hooks must be callable no-ops, not the originals.
        self.assertIsNone(LinuxDriver._query_in_band_window_resize(object()))
        self.assertIsNone(LinuxInlineDriver._query_in_band_window_resize(object()))

    @unittest.skipIf(
        termios is not None,
        "linux drivers are available; covered by test_both_linux_drivers_are_neutralised",
    )
    def test_linux_driver_patch_is_a_noop_without_termios(self):
        """Windows (and other non-POSIX hosts) must still apply the patch safely."""
        bootstrap._patch_textual_terminal_queries()

    def test_missing_textual_drivers_are_tolerated(self):
        with patch.dict(
            sys.modules,
            {
                "textual.drivers.linux_driver": None,
                "textual.drivers.linux_inline_driver": None,
            },
        ):
            # Must not raise even though neither driver can be imported.
            bootstrap._patch_textual_terminal_queries()


class TestLaunchTuiDefault(unittest.TestCase):
    def _ctx(self, validate_error=None):
        config = MagicMock()
        if validate_error is not None:
            config.validate.side_effect = validate_error
        ctx = MagicMock()
        ctx.obj = {"config": config}
        return ctx, config

    def test_incomplete_configuration_shows_welcome_instead_of_tui(self):
        ctx, config = self._ctx(validate_error=ValueError("API key is required"))

        with (
            patch.object(bootstrap, "_display_welcome") as welcome,
            patch.object(bootstrap.console, "print") as printer,
        ):
            bootstrap._launch_tui_default(ctx)

        welcome.assert_called_once_with()
        ctx.exit.assert_not_called()
        printed = " ".join(
            str(call.args[0]) for call in printer.call_args_list if call.args
        )
        self.assertIn("Configuration not complete", printed)
        self.assertIn("hackagent init", printed)

    def test_valid_configuration_runs_the_tui_app(self):
        ctx, config = self._ctx()
        app = MagicMock()

        with (
            patch("hackagent.cli.tui.HackAgentTUI", return_value=app) as tui_cls,
            patch.object(bootstrap, "_patch_textual_terminal_queries") as patcher,
        ):
            bootstrap._launch_tui_default(ctx)

        patcher.assert_called_once_with()
        tui_cls.assert_called_once_with(config)
        app.run.assert_called_once_with()
        ctx.exit.assert_not_called()

    def test_missing_tui_dependency_exits_with_install_hint(self):
        ctx, _ = self._ctx()

        with (
            patch.dict(sys.modules, {"hackagent.cli.tui": None}),
            patch.object(bootstrap.console, "print") as printer,
        ):
            bootstrap._launch_tui_default(ctx)

        ctx.exit.assert_called_once_with(1)
        printed = " ".join(
            str(call.args[0]) for call in printer.call_args_list if call.args
        )
        self.assertIn("TUI dependencies not installed", printed)
        self.assertIn("pip install textual", printed)

    def test_tui_startup_failure_exits_with_cli_hint(self):
        ctx, _ = self._ctx()

        with (
            patch("hackagent.cli.tui.HackAgentTUI", side_effect=RuntimeError("no tty")),
            patch.object(bootstrap, "_patch_textual_terminal_queries"),
            patch.object(bootstrap.console, "print") as printer,
        ):
            bootstrap._launch_tui_default(ctx)

        ctx.exit.assert_called_once_with(1)
        printed = " ".join(
            str(call.args[0]) for call in printer.call_args_list if call.args
        )
        self.assertIn("TUI failed to start", printed)
        self.assertIn("no tty", printed)

    def test_app_run_failure_is_also_handled(self):
        ctx, _ = self._ctx()
        app = MagicMock()
        app.run.side_effect = RuntimeError("driver crashed")

        with (
            patch("hackagent.cli.tui.HackAgentTUI", return_value=app),
            patch.object(bootstrap, "_patch_textual_terminal_queries"),
            patch.object(bootstrap.console, "print"),
        ):
            bootstrap._launch_tui_default(ctx)

        ctx.exit.assert_called_once_with(1)


class TestDisplayWelcome(unittest.TestCase):
    def test_welcome_renders_splash_and_getting_started_panel(self):
        with (
            patch("hackagent.cli.banner.display_hackagent_splash") as splash,
            patch.object(bootstrap.console, "print") as printer,
        ):
            bootstrap._display_welcome()

        splash.assert_called_once_with()
        printer.assert_called_once()
        panel = printer.call_args.args[0]
        self.assertIn("HackAgent CLI", str(panel.title))
        self.assertIn("hackagent init", panel.renderable)
        self.assertIn("hackagent web", panel.renderable)


if __name__ == "__main__":
    unittest.main()
