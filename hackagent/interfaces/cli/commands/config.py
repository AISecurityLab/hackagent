# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Configuration Commands

Manage HackAgent CLI configuration settings.
"""

import click
from rich.console import Console
from rich.table import Table

from hackagent.interfaces.cli.config import CLIConfig
from hackagent.core.settings import Source
from hackagent.interfaces.cli.utils import display_info, display_success, handle_errors
from hackagent import resolve_remote_base_url
from hackagent.core.settings import tls_error_hint

console = Console()


@click.group()
def config():
    """🔧 Manage HackAgent CLI configuration"""
    pass


@config.command()
@click.option(
    "--backend",
    type=click.Choice(["local", "remote"]),
    help="Default storage backend (remote reads the key from HACKAGENT_API_KEY)",
)
@click.option("--base-url", help="HackAgent API base URL")
@click.option(
    "--ca-bundle",
    type=click.Path(exists=True, dir_okay=True),
    help="CA bundle (PEM) trusted for the HackAgent API",
)
@click.option(
    "--verbose",
    type=str,
    help="Default verbosity level: 0/error, 1/warning, 2/info, 3/debug",
)
@click.pass_context
@handle_errors
def set(ctx, backend, base_url, ca_bundle, verbose):
    """Set storage, API location, CA bundle and verbosity defaults"""

    cli_config: CLIConfig = ctx.obj["config"]

    updated = False

    if backend:
        cli_config.set_user_override("backend", backend)
        updated = True
        if cli_config.should_show_info():
            display_success(f"Storage backend updated to: {backend}")

    if base_url:
        cli_config.set_user_override("base_url", base_url)
        updated = True
        if cli_config.should_show_info():
            display_success(f"Base URL updated to: {base_url}")

    if ca_bundle:
        from pathlib import Path

        cli_config.set_user_override("ca_bundle", str(Path(ca_bundle).resolve()))
        updated = True
        if cli_config.should_show_info():
            display_success(f"CA bundle updated to: {cli_config.ca_bundle}")

    if verbose is not None:
        from hackagent.interfaces.cli.config import VERBOSITY_LEVELS, VERBOSITY_NAMES

        try:
            verbose_int = int(verbose)
            if 0 <= verbose_int <= 3:
                cli_config.set_user_override("verbose", verbose_int)
                updated = True
                if cli_config.verbose > 0:
                    display_success(
                        f"Verbosity level updated to: {verbose_int} ({VERBOSITY_NAMES[verbose_int]})"
                    )
            else:
                display_info("Verbosity level must be between 0 and 3")
        except ValueError:
            verbose_lower = verbose.lower()
            if verbose_lower in VERBOSITY_LEVELS:
                verbose_int = VERBOSITY_LEVELS[verbose_lower]
                cli_config.set_user_override("verbose", verbose_int)
                updated = True
                if cli_config.verbose > 0:
                    display_success(
                        f"Verbosity level updated to: {verbose_int} ({VERBOSITY_NAMES[verbose_int]})"
                    )
            else:
                display_info(
                    f"Invalid verbosity level. Use: 0-3 or {', '.join(VERBOSITY_LEVELS.keys())}"
                )

    if updated:
        cli_config.save()
        display_success("✅ Configuration saved")
    else:
        display_info("No configuration changes made")


@config.command()
@click.pass_context
@handle_errors
def show(ctx):
    """Show current configuration"""

    cli_config: CLIConfig = ctx.obj["config"]

    table = Table(
        title="HackAgent Configuration", show_header=True, header_style="bold cyan"
    )
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Source", style="dim")

    api_key_display = "Set" if cli_config.api_key else "Not set"
    api_key_source = cli_config.source_of("api_key")
    from hackagent.interfaces.cli.config import VERBOSITY_NAMES

    table.add_row(
        "Storage Backend", cli_config.backend, cli_config.source_of("backend")
    )
    table.add_row("API Key", api_key_display, api_key_source)
    table.add_row("Base URL", cli_config.base_url, cli_config.source_of("base_url"))
    verbosity_display = (
        f"{cli_config.verbose} ({VERBOSITY_NAMES.get(cli_config.verbose, 'UNKNOWN')})"
    )
    table.add_row("Verbosity", verbosity_display, "Default/Config")
    table.add_row(
        "Config File", str(cli_config.default_config_path), "Default location"
    )

    console.print(table)

    if cli_config.should_show_info():
        if cli_config.default_config_path.exists():
            display_info(f"Configuration file: {cli_config.default_config_path}")
        else:
            display_info(
                "No configuration file found. Use 'hackagent config set' to create one."
            )


@config.command()
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
@handle_errors
def reset(ctx, confirm):
    """Reset configuration to defaults"""

    cli_config: CLIConfig = ctx.obj["config"]

    if not confirm:
        if not click.confirm(
            "⚠️ This will reset all configuration to defaults. Continue?"
        ):
            display_info("Configuration reset cancelled")
            return

    if cli_config.default_config_path.exists():
        cli_config.default_config_path.unlink()
        display_success("✅ Configuration reset to defaults")
        if cli_config.should_show_info():
            display_info(
                "API keys are read from environment variables (HACKAGENT_API_KEY by default)"
            )
    else:
        display_info("No configuration file to reset")


@config.command()
@click.pass_context
@handle_errors
def validate(ctx):
    """Validate current configuration"""

    cli_config: CLIConfig = ctx.obj["config"]

    try:
        cli_config.validate()

        from contextlib import nullcontext

        from hackagent import HackAgent

        session = HackAgent(cli_config.settings)
        spinner = (
            console.status("[bold green]Testing API connection...")
            if cli_config.should_show_info()
            else nullcontext()
        )
        with spinner:
            status_code = session.check_connection()

        if status_code == 200:
            display_success("✅ Configuration valid - API connection successful")
        else:
            console.print(
                f"[yellow]⚠️ Configuration valid but API connection issue: Status {status_code}"
            )

    except ValueError as e:
        console.print(f"[red]❌ Configuration validation failed: {e}")
        console.print("\n[cyan]💡 Quick fixes:")
        console.print("  • Set API key: export HACKAGENT_API_KEY=...")
        console.print(
            f"  • Set base URL: hackagent config set --base-url {resolve_remote_base_url()}"
        )
        raise click.ClickException("Configuration validation failed")
    except Exception as e:
        console.print(f"[yellow]⚠️ Could not test API connection: {e}")
        hint = tls_error_hint(e)
        if hint:
            console.print(f"[yellow]{hint}")
        display_info(
            "Configuration appears valid, but API connection could not be tested"
        )


@config.command()
@click.argument("config_file", type=click.Path(exists=True))
@click.pass_context
@handle_errors
def import_config(ctx, config_file):
    """Import configuration from a file"""

    from hackagent.interfaces.cli.utils import load_config_file

    try:
        config_data = load_config_file(config_file)

        cli_config: CLIConfig = ctx.obj["config"]

        updated_fields = []
        from hackagent.core.credentials import prepare_credentials

        config_data = prepare_credentials(config_data, from_file=True)
        if "api_key" in config_data:
            cli_config.set_user_override("api_key", config_data["api_key"])
            cli_config._sources["api_key"] = Source.FILE
            updated_fields.append("API key reference")

        if config_data.get("backend") in ("local", "remote"):
            cli_config.set_user_override("backend", config_data["backend"])
            updated_fields.append("Storage backend")

        if "base_url" in config_data:
            cli_config.base_url = config_data["base_url"]
            updated_fields.append("Base URL")

        if "ca_bundle" in config_data:
            cli_config.set_user_override("ca_bundle", config_data["ca_bundle"])
            updated_fields.append("CA bundle")

        if "verbose" in config_data:
            cli_config.verbose = config_data["verbose"]
            updated_fields.append("Verbosity")

        if updated_fields:
            cli_config.save()
            display_success(f"✅ Configuration imported: {', '.join(updated_fields)}")
            if cli_config.should_show_info():
                display_info(f"Saved to: {cli_config.default_config_path}")
        else:
            display_info("No valid configuration found in file")

    except Exception as e:
        raise click.ClickException(f"Failed to import configuration: {e}")
