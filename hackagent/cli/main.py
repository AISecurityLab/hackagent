# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
HackAgent CLI Main Entry Point

Main command-line interface for HackAgent security testing toolkit.
"""

import importlib.util
import os

import click
from rich.console import Console
from rich.traceback import install

from hackagent._version import get_version
from hackagent.cli.commands import (
    attack,
    claude as claude_cmd,
    codex as codex_cmd,
    datasets as datasets_cmd,
    examples,
    results,
    scan as scan_cmd,
    web as web_cmd,
)
from hackagent.cli.commands import (
    agent,
    config,
)
from hackagent.cli.bootstrap import (
    _launch_tui_default,
    _patch_textual_terminal_queries,
)
from hackagent.cli.config import CLIConfig
from hackagent.cli.help_page import _help_option_callback
from hackagent.cli.utils import display_info, handle_errors

# Install rich traceback handler for better error display
install(show_locals=True)

console = Console()


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
@click.version_option(version=get_version(), prog_name="hackagent")
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

    # Mode and API key setup
    console.print("\n[cyan]☁️ Mode Configuration[/cyan]")
    console.print("[green]Local mode (default):[/green] no API key required")
    console.print(
        "[green]Remote mode:[/green] requires HackAgent API key for cloud sync"
    )

    use_remote = click.confirm(
        "Enable remote mode (cloud sync)?",
        default=False,
    )

    if use_remote:
        if cli_config.api_key:
            console.print(
                "[dim]Press Enter to keep your current API key from config/environment.[/dim]"
            )

        api_key_input = click.prompt(
            "HackAgent API key",
            default=cli_config.api_key or "",
            hide_input=True,
            show_default=False,
        ).strip()

        if api_key_input:
            cli_config.api_key = api_key_input
        else:
            console.print(
                "[yellow]⚠️ No API key provided. Falling back to local mode.[/yellow]"
            )
            cli_config.api_key = None
    else:
        cli_config.api_key = None

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
    cli_config.verbose = verbose_level

    try:
        cli_config.save()
        console.print("\n[bold green]✅ Configuration saved[/bold green]")

        console.print("\n[cyan]🧩 FC-Attack Graphviz Setup[/cyan]")
        console.print(
            "[dim]Graphviz is needed only for FC-Attack image rendering. "
            "tFC-Attack does not require it.[/dim]"
        )

        try:
            from hackagent.attacks.techniques.fc.flowchart_renderer import (
                ensure_graphviz_dot_available,
            )

            existing_dot = ensure_graphviz_dot_available(allow_download=False)
            if existing_dot:
                console.print(
                    f"[green]✅ Graphviz detected:[/green] [dim]{existing_dot}[/dim]"
                )
            else:
                should_prefetch = click.confirm(
                    "Graphviz not found. Download portable binaries now for FC-Attack?",
                    default=True,
                )

                if should_prefetch:
                    dot_path = ensure_graphviz_dot_available(allow_download=True)
                    if dot_path:
                        console.print(
                            f"[green]✅ Graphviz ready:[/green] [dim]{dot_path}[/dim]"
                        )
                    else:
                        console.print(
                            "[yellow]⚠️ Could not prepare Graphviz automatically. "
                            "You can still use tFC-Attack or set "
                            "HACKAGENT_GRAPHVIZ_DOT later.[/yellow]"
                        )
                else:
                    console.print(
                        "[dim]Skipped Graphviz prefetch. "
                        "You can run FC-Attack setup later via HACKAGENT_GRAPHVIZ_DOT "
                        "or by re-running init.[/dim]"
                    )
        except Exception as graphviz_exc:
            console.print(
                "[yellow]⚠️ Graphviz setup check failed during init:[/yellow] "
                f"[dim]{graphviz_exc}[/dim]"
            )

        if cli_config.api_key:
            console.print(
                "[bold green]✅ Setup complete![/bold green] "
                "[dim](Remote mode enabled: runs can sync to the HackAgent platform)[/dim]"
            )
        else:
            console.print(
                "[bold green]✅ Setup complete![/bold green] "
                "[dim](Local mode: results stored in ~/.local/share/hackagent/hackagent.db)[/dim]"
            )
        if cli_config.should_show_info():
            console.print("\n[bold cyan]💡 Next steps:[/bold cyan]")
            console.print("  [green]hackagent eval advprefix --help[/green]")
            console.print("  [green]hackagent agent list[/green]")

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

    console.print(f"[bold cyan]HackAgent CLI v{get_version()}[/bold cyan]")
    console.print(
        "[bold green]Python Security Testing Toolkit for AI Agents[/bold green]"
    )
    console.print()

    # Show configuration status
    cli_config: CLIConfig = ctx.obj["config"]

    console.print(f"[cyan]Config file:[/cyan] {cli_config.default_config_path}")

    console.print()
    console.print("[dim]For more information, run: hackagent --help")


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
        console.print("  Run '[green]hackagent init[/green]' to set up configuration")
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

    # Check 2: Storage
    console.print("\n[cyan]💾 Local Storage")
    from pathlib import Path

    db_path = Path.home() / ".local" / "share" / "hackagent" / "hackagent.db"
    if db_path.exists():
        console.print("[green]✅ Local database exists")
    else:
        console.print("[yellow]⚠️ No local database yet (will be created on first run)")

    # Check 3: API key
    console.print("\n[cyan]🔐 API Key")
    if cli_config.api_key:
        console.print("[green]✅ API key is set")
    else:
        console.print("[yellow]⚠️ API key not set")

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


cli.add_command(attack.eval_cmd)
cli.add_command(scan_cmd.scan)
cli.add_command(claude_cmd.claude)
cli.add_command(codex_cmd.codex)
cli.add_command(datasets_cmd.datasets)
cli.add_command(examples.examples)
cli.add_command(results.results)
cli.add_command(web_cmd.web)


if __name__ == "__main__":
    cli()


# Add command groups
cli.add_command(config.config)
cli.add_command(agent.agent)
