# Copyright 2025 - AI4I. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Configuration Commands

Manage HackAgent CLI configuration settings.
"""

import click
from rich.console import Console
from rich.table import Table

from hackagent.cli.config import CLIConfig
from hackagent.cli.utils import display_info, display_success, handle_errors

console = Console()


@click.group()
def config():
    """🔧 Manage HackAgent CLI configuration"""
    pass


@config.command()
@click.option("--api-key", help="HackAgent API key")
@click.option("--base-url", help="HackAgent API base URL")
@click.option(
    "--output-format",
    type=click.Choice(["table", "json", "csv"]),
    help="Default output format",
)
@click.pass_context
@handle_errors
def set(ctx, api_key, base_url, output_format):
    """Set configuration values"""

    cli_config: CLIConfig = ctx.obj["config"]

    updated = False

    if api_key:
        cli_config.api_key = api_key
        updated = True
        display_success("API key updated")

    if base_url:
        cli_config.base_url = base_url
        updated = True
        display_success(f"Base URL updated to: {base_url}")

    if output_format:
        cli_config.output_format = output_format
        updated = True
        display_success(f"Output format updated to: {output_format}")

    if updated:
        cli_config.save()
        display_success(f"Configuration saved to: {cli_config.default_config_path}")
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

    # Determine sources
    api_key_source = "Not set"
    if cli_config.api_key:
        if ctx.params.get("api_key"):
            api_key_source = "CLI argument"
        elif cli_config.config_file:
            api_key_source = f"Config file ({cli_config.config_file})"
        else:
            api_key_source = "Environment/Default config"

    base_url_source = "Default"
    if cli_config.base_url != "https://api.hackagent.dev":
        if ctx.params.get("base_url"):
            base_url_source = "CLI argument"
        elif cli_config.config_file:
            base_url_source = f"Config file ({cli_config.config_file})"
        else:
            base_url_source = "Environment/Default config"

    # Add rows
    api_key_display = (
        cli_config.api_key[:8] + "..." if cli_config.api_key else "Not set"
    )
    table.add_row("API Key", api_key_display, api_key_source)
    table.add_row("Base URL", cli_config.base_url, base_url_source)
    table.add_row("Output Format", cli_config.output_format, "Default/Config")
    table.add_row(
        "Config File", str(cli_config.default_config_path), "Default location"
    )

    console.print(table)

    # Show config file status
    if cli_config.default_config_path.exists():
        display_info(f"Configuration file exists: {cli_config.default_config_path}")
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

    # Remove config file if it exists
    if cli_config.default_config_path.exists():
        cli_config.default_config_path.unlink()
        display_success(f"Configuration file removed: {cli_config.default_config_path}")

    display_success("Configuration reset to defaults")
    display_info(
        "API key will need to be set again using environment variable or 'hackagent config set --api-key'"
    )


@config.command()
@click.pass_context
@handle_errors
def validate(ctx):
    """Validate current configuration"""

    cli_config: CLIConfig = ctx.obj["config"]

    try:
        cli_config.validate()
        display_success("✅ Configuration is valid")

        # Test API connection
        with console.status("[bold green]Testing API connection..."):
            from hackagent.client import AuthenticatedClient

            client = AuthenticatedClient(
                base_url=cli_config.base_url, token=cli_config.api_key, prefix="Bearer"
            )

            # Try to make a simple API call to test connection
            from hackagent.api.key import key_list

            response = key_list.sync_detailed(client=client)

            if response.status_code == 200:
                display_success("🌐 API connection successful")
            else:
                console.print(
                    f"[yellow]⚠️ API connection issue: Status {response.status_code}"
                )

    except ValueError as e:
        console.print(f"[red]❌ Configuration validation failed: {e}")
        console.print("\n[cyan]💡 Quick fixes:")
        console.print("  • Set API key: hackagent config set --api-key YOUR_KEY")
        console.print(
            "  • Set base URL: hackagent config set --base-url https://api.hackagent.dev"
        )
        raise click.ClickException("Configuration validation failed")
    except Exception as e:
        console.print(f"[yellow]⚠️ Could not test API connection: {e}")
        display_info(
            "Configuration appears valid, but API connection could not be tested"
        )


@config.command()
@click.argument("config_file", type=click.Path(exists=True))
@click.pass_context
@handle_errors
def import_config(ctx, config_file):
    """Import configuration from a file"""

    from hackagent.cli.utils import load_config_file

    try:
        config_data = load_config_file(config_file)

        cli_config: CLIConfig = ctx.obj["config"]

        # Update configuration
        updated_fields = []
        if "api_key" in config_data:
            cli_config.api_key = config_data["api_key"]
            updated_fields.append("API key")

        if "base_url" in config_data:
            cli_config.base_url = config_data["base_url"]
            updated_fields.append("Base URL")

        if "output_format" in config_data:
            cli_config.output_format = config_data["output_format"]
            updated_fields.append("Output format")

        if updated_fields:
            cli_config.save()
            display_success(f"Imported configuration: {', '.join(updated_fields)}")
            display_success(f"Configuration saved to: {cli_config.default_config_path}")
        else:
            display_info("No valid configuration found in file")

    except Exception as e:
        raise click.ClickException(f"Failed to import configuration: {e}")
