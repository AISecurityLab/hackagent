# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Default TUI launch, welcome screen and terminal compatibility patches."""

from rich.console import Console
from rich.panel import Panel

from hackagent.cli.config import CLIConfig

console = Console()


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
        # If validation fails, show welcome message instead
        console.print("[yellow]⚠️ Configuration not complete.[/yellow]")
        console.print()
        _display_welcome()
        console.print()
        console.print(
            "[cyan]Run '[bold]hackagent init[/bold]' to get started, or '[bold]hackagent --help[/bold]' for more options.[/cyan]"
        )
        return

    try:
        from hackagent.cli.tui import HackAgentTUI

        # Launch TUI
        _patch_textual_terminal_queries()
        app = HackAgentTUI(cli_config)
        app.run()

    except ImportError:
        console.print("[bold red]❌ TUI dependencies not installed[/bold red]")
        console.print("\n[cyan]💡 Install with:[/cyan]")
        console.print("  uv add textual")
        console.print("  # or")
        console.print("  pip install textual")
        ctx.exit(1)
    except Exception as e:
        console.print(f"[bold red]❌ TUI failed to start: {e}[/bold red]")
        console.print("\n[cyan]You can still use CLI commands:[/cyan]")
        console.print("  hackagent --help")
        ctx.exit(1)


def _display_welcome():
    """Display welcome message and basic usage info"""

    # Display HackAgent splash
    from hackagent.utils import display_hackagent_splash

    display_hackagent_splash()

    welcome_text = """[bold cyan]Welcome to HackAgent CLI![/bold cyan] 🔍

[green]A powerful toolkit for testing AI agent security through automated attacks.[/green]

[bold yellow]🚀 Getting Started:[/bold yellow]
  1. Configure preferences:    [cyan]hackagent init[/cyan]
  2. Launch full-screen TUI:   [cyan]hackagent[/cyan] (default) or [cyan]hackagent tui[/cyan]
  3. List available agents:    [cyan]hackagent agent list[/cyan]
    4. Run security tests:       [cyan]hackagent eval advprefix --help[/cyan]
  5. View results:             [cyan]hackagent results list[/cyan]
  6. Open web dashboard:       [cyan]hackagent web[/cyan]

[bold blue]💡 Need help?[/bold blue] Use '[cyan]hackagent --help[/cyan]' or '[cyan]hackagent COMMAND --help[/cyan]'"""

    panel = Panel(
        welcome_text, title="🔍 HackAgent CLI", border_style="red", padding=(1, 2)
    )
    console.print(panel)
