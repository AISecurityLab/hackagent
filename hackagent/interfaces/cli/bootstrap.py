# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Default TUI launch, welcome screen and terminal compatibility patches."""

from hackagent.interfaces.cli.config import CLIConfig
from hackagent.interfaces.cli.utils import (
    console,
    display_error,
    display_hint,
    display_warning,
)


def _patch_textual_terminal_queries() -> None:
    """Apply compatibility patch for terminals that leak '\x1b[?2048$p' as a visible 'p'."""
    try:
        from textual.drivers.linux_driver import LinuxDriver

        LinuxDriver._query_in_band_window_resize = lambda self: None
    except Exception:
        pass

    try:
        from textual.drivers.linux_inline_driver import LinuxInlineDriver

        LinuxInlineDriver._query_in_band_window_resize = lambda self: None
    except Exception:
        pass


def _launch_tui_default(ctx):
    """Launch TUI by default when no subcommand is provided"""
    cli_config: CLIConfig = ctx.obj["config"]

    try:
        # Try to validate configuration
        cli_config.validate()
    except ValueError:
        # Not set up yet: say what HackAgent is and how to start, instead.
        display_warning("Configuration not complete.")
        console.print()
        _display_welcome()
        return

    try:
        from hackagent.interfaces.tui import HackAgentTUI

        # Launch TUI
        _patch_textual_terminal_queries()
        app = HackAgentTUI(cli_config)
        app.run()

    except ImportError as e:
        display_error(f"The terminal app needs its dependencies: {e}")
        display_hint("Install them", "pip install 'hackagent[tui]'")
        ctx.exit(1)
    except Exception as e:
        display_error(f"The terminal app failed to start: {e}")
        display_hint("Every command still works", "hackagent --help")
        ctx.exit(1)


def _display_welcome():
    """The logo, and how to start: setting up, then a first campaign."""
    from hackagent.interfaces.brand import QUICK_START
    from hackagent.interfaces.cli.banner import display_hackagent_splash

    display_hackagent_splash(console)
    display_hint("Set up", "hackagent init")
    for what, command in QUICK_START:
        display_hint(what, command)
    display_hint("Every command", "hackagent --help")
