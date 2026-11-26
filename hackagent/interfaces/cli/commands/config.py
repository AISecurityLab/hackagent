# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Configuration Commands

Manage HackAgent CLI configuration settings.
"""

import click
from rich.table import Table

from hackagent.interfaces.cli.config import CLIConfig
from hackagent.core.settings import Source
from hackagent.interfaces.cli.utils import (
    Failed,
    console,
    display_info,
    display_success,
    display_warning,
    handle_errors,
)


@click.group()
def config():
    """Show and change the CLI's settings."""


def _setting(key: str) -> str:
    """What a setting is for, as its option's help."""
    from hackagent.interfaces.setup import SETTINGS

    return next(setting.help for setting in SETTINGS if setting.key == key)


@config.command()
@click.option(
    "--backend", type=click.Choice(["local", "remote"]), help=_setting("backend")
)
@click.option("--base-url", help=_setting("base_url"))
@click.option(
    "--ca-bundle",
    type=click.Path(exists=True, dir_okay=True),
    help=_setting("ca_bundle"),
)
@click.option("--verbosity", type=str, help=_setting("verbosity"))
@click.pass_context
@handle_errors
def set(ctx, backend, base_url, ca_bundle, verbosity):
    """Set storage, API location, CA bundle and verbosity defaults

    The terminal app's Settings screen changes the same settings.
    """
    from hackagent.interfaces.setup import change_settings

    cli_config: CLIConfig = ctx.obj["config"]
    changed, refused = change_settings(
        cli_config,
        {
            "backend": backend,
            "base_url": base_url,
            "ca_bundle": ca_bundle,
            "verbosity": verbosity,
        },
    )
    for problem in refused:
        display_warning(problem)
    for change in changed:
        display_success(change)
    updated = bool(changed)

    if updated:
        cli_config.save()
        display_success("Configuration saved")
    else:
        display_info("No configuration changes made")


@config.command()
@click.pass_context
@handle_errors
def show(ctx):
    """Show current configuration"""

    cli_config: CLIConfig = ctx.obj["config"]

    from hackagent.interfaces.cli.config import VERBOSITY

    # By the keys `hackagent config set` and the configuration file use.
    table = Table(title="Configuration", show_header=True, header_style="heading")
    table.add_column("Setting", style="accent")
    table.add_column("Value")
    table.add_column("From", style="secondary")
    table.add_row("backend", cli_config.backend, cli_config.source_of("backend"))
    table.add_row(
        "api_key",
        "set" if cli_config.api_key else "not set",
        cli_config.source_of("api_key"),
    )
    table.add_row("base_url", cli_config.base_url, cli_config.source_of("base_url"))
    table.add_row(
        "ca_bundle",
        str(cli_config.ca_bundle or "—"),
        cli_config.source_of("ca_bundle"),
    )
    table.add_row(
        "verbosity",
        f"{cli_config.verbose} ({VERBOSITY[cli_config.verbose]})",
        cli_config.source_of("verbose"),
    )
    console.print(table)
    path = cli_config.default_config_path
    display_info(
        f"Configuration file: {path}"
        if path.exists()
        else f"No configuration file at {path}: hackagent config set creates it."
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
            "This will reset all configuration to defaults. Continue?"
        ):
            display_info("Configuration reset cancelled")
            return

    if cli_config.default_config_path.exists():
        cli_config.default_config_path.unlink()
        display_success("Configuration reset to defaults")
        display_info("The API key is read from HACKAGENT_API_KEY.")
    else:
        display_info("No configuration file to reset")


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

        from hackagent.interfaces.cli.config import _from_file

        verbosity = _from_file(config_data)
        if verbosity is not None:
            cli_config.set_user_override("verbosity", verbosity)
            updated_fields.append("Verbosity")

        if updated_fields:
            cli_config.save()
            display_success(f"Configuration imported: {', '.join(updated_fields)}")
            display_info(f"Saved to: {cli_config.default_config_path}")
        else:
            display_info("No valid configuration found in file")

    except Exception as e:
        raise Failed(f"Failed to import configuration: {e}") from e
