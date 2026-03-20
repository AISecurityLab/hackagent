# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
HackAgent CLI Main Entry Point

Main command-line interface for HackAgent security testing toolkit.
"""

import importlib.metadata
import importlib.util
import os

import click
from rich.console import Console
from rich.panel import Panel
from rich.traceback import install

from hackagent.cli.commands import (
    agent,
    attack,
    config,
    examples,
    results,
    web as web_cmd,
)
from hackagent.cli.config import CLIConfig
from hackagent.cli.utils import display_info, handle_errors

# Install rich traceback handler for better error display
install(show_locals=True)

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


def _render_rich_help(ctx: click.Context) -> None:
    """Print the Rich-formatted help page for the main CLI group."""
    from rich.rule import Rule
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.text import Text

    from hackagent.utils import HACKAGENT

    c = Console()
    version = importlib.metadata.version("hackagent")

    # ── Logo ──────────────────────────────────────────────────────────────────
    c.print(
        Panel(
            Text(HACKAGENT, style="bold dark_red"),
            border_style="red",
            padding=(0, 2),
            expand=False,
        )
    )
    c.print(
        f"  [bold white]HackAgent CLI[/bold white] [dim]v{version}[/dim]"
        f"  [dim]·[/dim]  [italic cyan]AI Agent Security Testing Toolkit[/italic cyan]\n"
    )

    # ── Quick Start ───────────────────────────────────────────────────────────
    c.print(Rule("[bold]Quick Start[/bold]", style="dim"))
    qs_code = (
        "# 1. Interactive first-time setup\n"
        "hackagent init\n\n"
        "# 2. Register a target agent\n"
        'hackagent agent create --name "my-bot" --type google-adk \\\n'
        "    --endpoint http://localhost:8000\n\n"
        "# 3. Run an adversarial attack\n"
        'hackagent attack advprefix --agent-name "my-bot" \\\n'
        '    --goals "Ignore safety rules"\n\n'
        "# 4. Review findings\n"
        "hackagent results summary"
    )
    c.print(
        Panel(
            Syntax(qs_code, "bash", theme="monokai", background_color="default"),
            border_style="dim",
            padding=(0, 1),
        )
    )
    c.print()

    # ── Commands ──────────────────────────────────────────────────────────────
    c.print(Rule("[bold]Commands[/bold]", style="dim"))
    cmd_table = Table.grid(padding=(0, 3))
    cmd_table.add_column(style="bold cyan", no_wrap=True, min_width=12)
    cmd_table.add_column()
    group: click.Group = ctx.command  # type: ignore[assignment]
    for name in group.list_commands(ctx):
        cmd = group.get_command(ctx, name)
        if cmd is None:
            continue
        cmd_table.add_row(f"  {name}", cmd.get_short_help_str(limit=60) or "")
    c.print(cmd_table)
    c.print()

    # ── Options ───────────────────────────────────────────────────────────────
    c.print(Rule("[bold]Options[/bold]", style="dim"))
    opt_table = Table.grid(padding=(0, 3))
    opt_table.add_column(style="bold yellow", no_wrap=True, min_width=36)
    opt_table.add_column(style="dim")
    for param in ctx.command.params:
        if not isinstance(param, click.Option):
            continue
        decls = ", ".join(param.opts)
        if param.is_flag or param.count:  # type: ignore[union-attr]
            meta = ""
        elif param.metavar:
            meta = f" {param.metavar}"
        elif param.type is not None:
            meta = f" {param.type.name.upper()}"
        else:
            meta = ""
        opt_table.add_row(f"  {decls}{meta}", param.help or "")
    c.print(opt_table)
    c.print()

    # ── Environment Variables ─────────────────────────────────────────────────
    c.print(Rule("[bold]Environment Variables[/bold]", style="dim"))
    env_table = Table.grid(padding=(0, 3))
    env_table.add_column(style="bold magenta", no_wrap=True, min_width=24)
    env_table.add_column(style="dim")
    env_table.add_row("  HACKAGENT_API_KEY", "API key (overrides config file value)")
    env_table.add_row(
        "  HACKAGENT_BASE_URL", "API base URL (default: https://api.hackagent.dev)"
    )
    env_table.add_row(
        "  HACKAGENT_DEBUG", "Enable debug output (set to any non-empty value)"
    )
    c.print(env_table)
    c.print()

    # ── Operating Modes ───────────────────────────────────────────────────────
    c.print(Rule("[bold]Operating Modes[/bold]", style="dim"))
    mode_table = Table.grid(padding=(0, 3))
    mode_table.add_column(no_wrap=True, min_width=10)
    mode_table.add_column(style="dim")
    mode_table.add_row(
        "  [bold green]Local[/bold green]",
        "No API key needed — results stored in local SQLite database",
    )
    mode_table.add_row(
        "  [bold cyan]Cloud[/bold cyan]",
        "With HACKAGENT_API_KEY — results synced to HackAgent cloud",
    )
    c.print(mode_table)
    c.print()

    # ── Footer ────────────────────────────────────────────────────────────────
    c.print(Rule(style="dim"))
    c.print(
        "  [dim]Docs[/dim]  [link=https://docs.hackagent.dev]https://docs.hackagent.dev[/link]"
        "    [dim]API Keys[/dim]  [link=https://app.hackagent.dev]https://app.hackagent.dev[/link]\n"
    )


def _help_option_callback(
    ctx: click.Context, param: click.Parameter, value: bool
) -> None:
    if value and not ctx.resilient_parsing:
        _render_rich_help(ctx)
        ctx.exit()


@click.group(invoke_without_command=True, add_help_option=False)
@click.option(
    "--help",
    "-h",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_help_option_callback,
    help="Show this message and exit.",
)
@click.option(
    "--config-file", type=click.Path(), help="Configuration file path (JSON/YAML)"
)
@click.option(
    "--api-key",
    envvar="HACKAGENT_API_KEY",
    help="HackAgent API key (or set HACKAGENT_API_KEY)",
)
@click.option(
    "--base-url",
    envvar="HACKAGENT_BASE_URL",
    default="https://api.hackagent.dev",
    help="HackAgent API base URL",
)
@click.option("--verbose", "-v", count=True, help="Increase verbosity (-v, -vv, -vvv)")
@click.version_option(
    version=importlib.metadata.version("hackagent"), prog_name="hackagent"
)
@click.pass_context
def cli(ctx, config_file, api_key, base_url, verbose):
    ctx.ensure_object(dict)

    # Set debug mode based on environment variable
    if os.getenv("HACKAGENT_DEBUG"):
        os.environ["HACKAGENT_DEBUG"] = "1"

    # Set verbose level in environment for other modules
    if verbose:
        os.environ["HACKAGENT_VERBOSE"] = str(verbose)

    # Initialize CLI configuration
    try:
        ctx.obj["config"] = CLIConfig(
            config_file=config_file,
            api_key=api_key,
            base_url=base_url,
            verbose=verbose,
        )
    except Exception as e:
        console.print(f"[bold red]❌ Configuration Error: {e}")
        ctx.exit(1)

    # Launch TUI by default if no subcommand is provided
    if ctx.invoked_subcommand is None:
        _launch_tui_default(ctx)


@cli.command()
@click.pass_context
@handle_errors
def init(ctx):
    """🚀 Initialize HackAgent CLI configuration

    Interactive setup wizard for first-time users.
    """

    # Show the awesome logo first
    from hackagent.utils import display_hackagent_splash

    display_hackagent_splash()

    console.print("[bold cyan]🔧 HackAgent CLI Setup Wizard[/bold cyan]")
    console.print(
        "[green]Welcome! Let's get you set up for AI agent security testing.[/green]"
    )
    console.print()

    # Check if config already exists
    cli_config: CLIConfig = ctx.obj["config"]

    if cli_config.default_config_path.exists():
        if not click.confirm("Configuration already exists. Overwrite?"):
            display_info("Setup cancelled")
            return
        # Reload config from file to get the latest saved values
        cli_config._load_default_config()

    # API Key setup
    console.print("[cyan]📋 API Key Configuration[/cyan]")
    console.print(
        "Get your API key from: [link=https://app.hackagent.dev]https://app.hackagent.dev[/link]"
    )

    current_key = cli_config.api_key
    if current_key:
        console.print(f"Current API key: {current_key[:8]}...")
        if click.confirm("Keep current API key?"):
            api_key = current_key
        else:
            api_key = click.prompt(
                "Enter your API key (press Enter to skip)",
                default="",
                show_default=False,
            ).strip() or None
    else:
        api_key = click.prompt(
            "Enter your API key (press Enter to skip)",
            default="",
            show_default=False,
        ).strip() or None

    # Base URL is always the official endpoint
    base_url = "https://api.hackagent.dev"

    # Verbosity level setup
    console.print("\n[cyan]🔊 Verbosity Level Configuration[/cyan]")
    console.print("0 = ERROR (only errors)")
    console.print("1 = WARNING (errors + warnings) [default]")
    console.print("2 = INFO (errors + warnings + info)")
    console.print("3 = DEBUG (all messages)")
    verbose_level = click.prompt(
        "Default verbosity level",
        type=int,
        default=cli_config.verbose,
    )
    if not 0 <= verbose_level <= 3:
        console.print("[yellow]⚠️ Invalid verbosity level, using 1 (WARNING)[/yellow]")
        verbose_level = 1

    # Save configuration
    cli_config.api_key = api_key
    cli_config.base_url = base_url
    cli_config.verbose = verbose_level

    try:
        cli_config.save()
        console.print("\n[bold green]✅ Configuration saved[/bold green]")

        # Test the configuration
        if cli_config.should_show_info():
            console.print("\n[cyan]🔍 Testing configuration...[/cyan]")
        cli_config.validate()

        # API key is optional: if absent, keep local mode and skip remote check.
        if not cli_config.api_key:
            console.print(
                "[bold green]✅ Setup complete![/bold green] "
                "[dim](No API key set: local mode enabled)[/dim]"
            )
            if cli_config.should_show_info():
                console.print("\n[bold cyan]💡 Next steps:[/bold cyan]")
                console.print("  [green]hackagent attack advprefix --help[/green]")
                console.print("  [green]hackagent agent list[/green]")
            return

        # Test API connection when a key is configured.
        from hackagent.server.api.agent import agent_list
        from hackagent.server.client import AuthenticatedClient

        client = AuthenticatedClient(
            base_url=cli_config.base_url, token=cli_config.api_key, prefix="Bearer"
        )

        if cli_config.should_show_info():
            with console.status("[bold green]Testing API connection..."):
                response = agent_list.sync_detailed(client=client)
        else:
            response = agent_list.sync_detailed(client=client)

        if response.status_code == 200:
            console.print(
                "[bold green]✅ Setup complete! API connection verified.[/bold green]"
            )
            if response.parsed and cli_config.should_show_info():
                agent_count = (
                    len(response.parsed.results) if response.parsed.results else 0
                )
                console.print(
                    f"[dim]Found {agent_count} agent(s) in your organization[/dim]"
                )
            if cli_config.should_show_info():
                console.print("\n[bold cyan]💡 Next steps:[/bold cyan]")
                console.print("  [green]hackagent attack advprefix --help[/green]")
                console.print("  [green]hackagent agent list[/green]")
        else:
            console.print(
                f"[yellow]⚠️ API connection issue (Status: {response.status_code})[/yellow]"
            )
            console.print("Configuration saved, but you may need to check your API key")

    except Exception as e:
        console.print(f"[bold red]❌ Setup failed: {e}[/bold red]")
        ctx.exit(1)


@cli.command()
@click.pass_context
@handle_errors
def version(ctx):
    """📋 Show version information"""

    # Display the awesome ASCII logo
    from hackagent.utils import display_hackagent_splash

    display_hackagent_splash()

    console.print(
        f"[bold cyan]HackAgent CLI v{importlib.metadata.version('hackagent')}[/bold cyan]"
    )
    console.print(
        "[bold green]Python Security Testing Toolkit for AI Agents[/bold green]"
    )
    console.print()

    # Show configuration status
    cli_config: CLIConfig = ctx.obj["config"]

    config_status = (
        "[green]✅ Configured[/green]"
        if cli_config.api_key
        else "[red]❌ Not configured[/red]"
    )
    console.print(f"[cyan]Configuration:[/cyan] {config_status}")
    console.print(f"[cyan]Config file:[/cyan] {cli_config.default_config_path}")
    console.print(f"[cyan]API Base URL:[/cyan] {cli_config.base_url}")

    if cli_config.api_key:
        console.print(f"[cyan]API Key:[/cyan] {cli_config.api_key[:8]}...")

    console.print()
    console.print(
        "[dim]For more information: [link=https://docs.hackagent.dev]https://docs.hackagent.dev[/link]"
    )


@cli.command()
@click.pass_context
@handle_errors
def tui(ctx):
    """🖥️ Launch full-screen Terminal User Interface

    Opens an interactive tabbed interface that occupies the whole terminal.
    Navigate between tabs to manage agents, execute attacks, view results, and configure settings.

    \b
    Features:
      • Dashboard - Overview and statistics
      • Agents - Manage AI agents
      • Attacks - Execute security attacks
      • Results - View attack results
      • Config - Configuration management

    \b
    Keyboard Shortcuts:
      q - Quit
      F5 - Refresh current tab
      Tab - Navigate between UI elements
    """
    cli_config: CLIConfig = ctx.obj["config"]

    try:
        # Validate configuration before launching TUI
        cli_config.validate()
    except ValueError as e:
        console.print(f"[bold red]❌ Configuration Error: {e}[/bold red]")
        console.print("\n[cyan]💡 Quick fix:[/cyan]")
        console.print("  Run '[green]hackagent init[/green]' to set up your API key")
        ctx.exit(1)

    try:
        from hackagent.cli.tui import HackAgentTUI

        _patch_textual_terminal_queries()
        app = HackAgentTUI(cli_config)
        app.run()

    except ImportError:
        console.print("[bold red]❌ TUI dependencies not installed[/bold red]")
        console.print("\n[cyan]💡 Install with:[/cyan]")
        console.print("  pip install textual")
        ctx.exit(1)
    except Exception as e:
        console.print(f"[bold red]❌ TUI failed to start: {e}[/bold red]")
        ctx.exit(1)


@cli.command()
@click.pass_context
@handle_errors
def doctor(ctx):
    """🔍 Diagnose common configuration issues

    Checks your setup and provides helpful troubleshooting information.
    """
    console.print("[bold cyan]🔍 HackAgent CLI Diagnostics")
    console.print()

    cli_config: CLIConfig = ctx.obj["config"]
    issues_found = 0

    # Check 1: Configuration file
    console.print("[cyan]📋 Configuration File")
    if cli_config.default_config_path.exists():
        console.print("[green]✅ Configuration file exists")
    else:
        console.print("[yellow]⚠️ No configuration file found")
        console.print("   💡 Run 'hackagent init' to create one")
        issues_found += 1

    # Check 2: API Key
    console.print("\n[cyan]🔑 API Key")
    if cli_config.api_key:
        console.print("[green]✅ API key is set")

        # Test API key format
        if len(cli_config.api_key) > 20:
            console.print("[green]✅ API key format looks valid")
        else:
            console.print("[yellow]⚠️ API key seems too short")
            issues_found += 1
    else:
        console.print("[red]❌ API key not set")
        console.print("   💡 Set with: hackagent config set --api-key YOUR_KEY")
        console.print("   💡 Or set HACKAGENT_API_KEY environment variable")
        issues_found += 1

    # Check 3: API Connection
    console.print("\n[cyan]🌐 API Connection")
    if cli_config.api_key:
        try:
            from hackagent.server.api.agent import agent_list
            from hackagent.server.client import AuthenticatedClient

            client = AuthenticatedClient(
                base_url=cli_config.base_url, token=cli_config.api_key, prefix="Bearer"
            )

            with console.status("Testing API connection..."):
                response = agent_list.sync_detailed(client=client)

            if response.status_code == 200:
                console.print("[green]✅ API connection successful")
            else:
                console.print(
                    f"[red]❌ API connection failed (Status: {response.status_code})"
                )
                console.print("   💡 Check your API key and network connection")
                issues_found += 1

        except Exception as e:
            console.print(f"[red]❌ API connection error: {e}")
            console.print("   💡 Check your API key and network connection")
            issues_found += 1
    else:
        console.print("[dim]⏭️ Skipped (no API key)")

    # Check 4: Dependencies
    console.print("\n[cyan]📦 Dependencies")
    pandas_spec = importlib.util.find_spec("pandas")
    if pandas_spec is not None:
        console.print("[green]✅ pandas available")
    else:
        console.print("[red]❌ pandas not found")
        console.print("   💡 Install with: pip install pandas")
        issues_found += 1

    yaml_spec = importlib.util.find_spec("yaml")
    if yaml_spec is not None:
        console.print("[green]✅ PyYAML available")
    else:
        console.print("[yellow]⚠️ PyYAML not found (optional)")
        console.print("   💡 Install with: pip install pyyaml")

    # Summary
    console.print("\n[cyan]📊 Summary")
    if issues_found == 0:
        console.print(
            "[bold green]✅ All checks passed! You're ready to use HackAgent."
        )
    else:
        console.print(
            f"[bold yellow]⚠️ Found {issues_found} issue(s) that should be addressed."
        )
        console.print("\n[cyan]💡 Quick fixes:")
        console.print("  hackagent init          # Interactive setup")
        console.print("  hackagent config set    # Set specific values")
        console.print("  hackagent --help        # Show all commands")


def _launch_tui_default(ctx):
    """Launch TUI by default when no subcommand is provided"""
    cli_config: CLIConfig = ctx.obj["config"]

    try:
        # Try to validate configuration
        cli_config.validate()
    except ValueError:
        # If validation fails, show welcome message instead
        console.print(
            "[yellow]⚠️ Configuration not complete. Please set up your API key first.[/yellow]"
        )
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
  1. Set up your API key:     [cyan]hackagent init[/cyan]
  2. Launch full-screen TUI:  [cyan]hackagent[/cyan] (default) or [cyan]hackagent tui[/cyan]
  3. List available agents:   [cyan]hackagent agent list[/cyan]
  4. Run security tests:      [cyan]hackagent attack advprefix --help[/cyan]
  5. View results:            [cyan]hackagent results list[/cyan]

[bold blue]💡 Need help?[/bold blue] Use '[cyan]hackagent --help[/cyan]' or '[cyan]hackagent COMMAND --help[/cyan]'
[bold blue]🌐 Get your API key at:[/bold blue] [link=https://app.hackagent.dev]https://app.hackagent.dev[/link]"""

    panel = Panel(
        welcome_text, title="🔍 HackAgent CLI", border_style="red", padding=(1, 2)
    )
    console.print(panel)


# Add command groups
cli.add_command(config.config)
cli.add_command(agent.agent)
cli.add_command(attack.attack)
cli.add_command(examples.examples)
cli.add_command(results.results)
cli.add_command(web_cmd.web)


if __name__ == "__main__":
    cli()
