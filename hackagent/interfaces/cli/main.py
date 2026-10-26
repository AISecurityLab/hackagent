# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
HackAgent CLI Main Entry Point

Main command-line interface for HackAgent security testing toolkit.
"""

import os

import click
from rich.console import Console
from rich.traceback import install

from hackagent._version import get_version
from hackagent.core.credentials import CredentialError
from hackagent.interfaces.cli.commands import (
    campaign as campaign_cmd,
    datasets as datasets_cmd,
    examples,
    results,
    run as run_cmd,
    web as web_cmd,
)
from hackagent.interfaces.cli.commands import config
from hackagent.interfaces.cli.bootstrap import (
    _launch_tui_default,
    _patch_textual_terminal_queries,
)
from hackagent.interfaces.cli.config import CLIConfig
from hackagent.interfaces.cli.help_page import _help_option_callback
from hackagent.interfaces.cli.logging_setup import setup_package_logging
from hackagent.interfaces.cli.safe_stdio import (
    configure_safe_stdio,
    install_on_click_command,
)
from hackagent.interfaces.cli.utils import display_info, handle_errors

# Install rich traceback handler for better error display
install(show_locals=True)

console = Console()


class _CLIGroup(click.Group):
    """Apply subcommand storage overrides before resolving root settings."""

    def resolve_command(self, ctx, args):
        name, command, remaining = super().resolve_command(ctx, args)
        if name == "web":
            with command.make_context(
                name, list(remaining), parent=ctx, resilient_parsing=True
            ) as subcontext:
                if subcontext.params.get("force_local"):
                    ctx.params["backend"] = "local"
        return name, command, remaining


@click.group(cls=_CLIGroup, invoke_without_command=True, add_help_option=False)
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
    "--backend",
    type=click.Choice(["local", "remote"]),
    default=None,
    help="Storage backend (default: local, or HACKAGENT_BACKEND)",
)
@click.option(
    "--base-url",
    default=None,
    help="HackAgent API base URL (or set HACKAGENT_BASE_URL env var)",
)
@click.option(
    "--ca-bundle",
    default=None,
    type=click.Path(exists=True),
    help=(
        "CA bundle (PEM) trusted for the HackAgent API, e.g. a private CA "
        "(or set REQUESTS_CA_BUNDLE / SSL_CERT_FILE)"
    ),
)
@click.option("--verbose", "-v", count=True, help="Increase verbosity (-v, -vv, -vvv)")
@click.version_option(version=get_version(), prog_name="hackagent")
@click.pass_context
def cli(ctx, config_file, backend, base_url, ca_bundle, verbose):
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
            backend=backend,
            base_url=base_url,
            verbose=verbose,
            ca_bundle=ca_bundle,
        )
    except Exception as e:
        console.print(f"[bold red]❌ Configuration Error: {e}")
        if isinstance(e, CredentialError):
            console.print(
                "[dim]Set HACKAGENT_API_KEY or correct the api_key reference "
                "in the configuration file.[/dim]"
            )
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
    from hackagent.interfaces.cli.banner import display_hackagent_splash

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
        cli_config.reload()

    # Storage backend setup. API keys are never saved to the config file.
    console.print("\n[cyan]☁️ Storage Backend[/cyan]")
    console.print("[green]Local (default):[/green] results stay on this machine")
    console.print(
        "[green]Remote:[/green] results sync to the HackAgent platform; the API "
        "key is read from the HACKAGENT_API_KEY environment variable"
    )

    use_remote = click.confirm(
        "Use remote storage (cloud sync)?",
        default=cli_config.backend == "remote",
    )
    cli_config.set_user_override("backend", "remote" if use_remote else "local")
    if use_remote and not cli_config.api_key:
        console.print(
            "[yellow]⚠️ HACKAGENT_API_KEY is not set. Export it before running: "
            "remote storage fails without it.[/yellow]"
        )

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
            from hackagent.client import ensure_graphviz

            existing_dot = ensure_graphviz(allow_download=False)
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
                    dot_path = ensure_graphviz(allow_download=True)
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

        if cli_config.backend == "remote":
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
            console.print("  [green]hackagent campaign run --help[/green]")
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
    from hackagent.interfaces.cli.banner import display_hackagent_splash

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
    """🖥️ Launch the campaign builder

    Opens a full-screen app that builds a campaign, checks it as you type, and
    runs it. Start from a template or open an existing campaign.yaml.

    \b
    Keys:
      F1      what this screen is, and every key
      ctrl+r  run the campaign
      ctrl+s  save it to a file
      q       quit
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
        from hackagent.interfaces.tui import HackAgentTUI

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

    from hackagent import HackAgent

    # Diagnostics only read settings. A throwaway backend keeps doctor from
    # opening SQLite or the remote API, which would create the local database
    # before the "database exists" check.
    report = HackAgent(cli_config.settings, backend=object()).doctor()

    console.print("[cyan]📋 Configuration File")
    if report.config_exists:
        console.print("[green]✅ Configuration file exists")
    else:
        console.print("[yellow]⚠️ No configuration file found")
        console.print("   💡 Run 'hackagent init' to create one")

    console.print("\n[cyan]💾 Local Storage")
    if report.db_exists:
        console.print("[green]✅ Local database exists")
    else:
        console.print("[yellow]⚠️ No local database yet (will be created on first run)")

    console.print("\n[cyan]🗄️ Storage Backend")
    console.print(f"[green]{cli_config.backend}")

    console.print("\n[cyan]🔐 API Key")
    if report.api_key_set:
        console.print("[green]✅ API key is set")
    else:
        console.print("[yellow]⚠️ API key not set (export HACKAGENT_API_KEY)")

    console.print("\n[cyan]📦 Dependencies")
    if report.pandas_available:
        console.print("[green]✅ pandas available")
    else:
        console.print("[red]❌ pandas not found")
        console.print("   💡 Install with: pip install pandas")

    if report.yaml_available:
        console.print("[green]✅ PyYAML available")
    else:
        console.print("[yellow]⚠️ PyYAML not found (optional)")
        console.print("   💡 Install with: pip install pyyaml")

    console.print("\n[cyan]🧩 Graphviz")
    if report.graphviz_dot:
        console.print(
            f"[green]✅ Graphviz detected:[/green] [dim]{report.graphviz_dot}[/dim]"
        )
    elif report.graphviz_error:
        console.print(
            f"[yellow]⚠️ Graphviz check failed:[/yellow] [dim]{report.graphviz_error}[/dim]"
        )
    else:
        console.print("[yellow]⚠️ Graphviz not found (needed only for FC-Attack)")

    console.print("\n[cyan]📊 Summary")
    if not report.issues:
        console.print(
            "[bold green]✅ All checks passed! You're ready to use HackAgent."
        )
    else:
        console.print(
            f"[bold yellow]⚠️ Found {len(report.issues)} issue(s) that should be addressed."
        )
        console.print("\n[cyan]💡 Quick fixes:")
        console.print("  hackagent init          # Interactive setup")
        console.print("  hackagent config set    # Set specific values")
        console.print("  hackagent --help        # Show all commands")


cli.add_command(campaign_cmd.campaign)
cli.add_command(datasets_cmd.datasets)
cli.add_command(examples.examples)
cli.add_command(results.results)
cli.add_command(run_cmd.run)
cli.add_command(web_cmd.web)


# Add command groups
cli.add_command(config.config)

# Cover Click eager options (--version, --help) and the console-script entry.
install_on_click_command(cli)


def main() -> None:
    """Process entry for the ``hackagent`` console script and frozen binary."""
    configure_safe_stdio()
    setup_package_logging()
    cli()


if __name__ == "__main__":
    main()
