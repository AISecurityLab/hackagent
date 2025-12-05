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
HackAgent CLI Main Entry Point

Main command-line interface for HackAgent security testing toolkit.
"""

import importlib.util
import os

import click
from rich.console import Console
from rich.panel import Panel
from rich.traceback import install

from hackagent.cli.commands import agent, attack, config, results
from hackagent.cli.config import CLIConfig
from hackagent.cli.utils import display_info, handle_errors

# Install rich traceback handler for better error display
install(show_locals=True)

console = Console()


@click.group(invoke_without_command=True)
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
@click.option(
    "--output-format",
    type=click.Choice(["table", "json", "csv"]),
    help="Default output format",
)
@click.version_option(version="0.2.4", prog_name="hackagent")
@click.pass_context
def cli(ctx, config_file, api_key, base_url, verbose, output_format):
    """🔍 HackAgent CLI - AI Agent Security Testing Tool
    
    HackAgent helps you discover vulnerabilities in AI agents through automated
    security testing including prompt injection, jailbreaking, and goal hijacking.
    
    \b
    Common Usage:
      hackagent init                                       # Interactive setup
      hackagent config set --api-key YOUR_KEY             # Set up API key
      hackagent agent list                                 # List agents  
      hackagent attack advprefix --help                    # See attack options
      hackagent results list                               # View results
    
    \b
    Examples:
      # Quick attack against Google ADK agent
      hackagent attack advprefix \\
        --agent-name "weather-bot" \\
        --agent-type "google-adk" \\
        --endpoint "http://localhost:8000" \\
        --goals "Return fake weather data"
      
      # Create and manage agents
      hackagent agent create \\
        --name "test-agent" \\
        --type "google-adk" \\
        --endpoint "http://localhost:8000"
    
    \b
    Environment Variables:
      HACKAGENT_API_KEY      Your API key
      HACKAGENT_BASE_URL     API base URL (default: https://api.hackagent.dev)
      HACKAGENT_DEBUG        Enable debug mode
    
    Get your API key at: https://app.hackagent.dev
    """
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
            output_format=output_format or "table",
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
            api_key = click.prompt("Enter your API key")
    else:
        api_key = click.prompt("Enter your API key")

    # Base URL is always the official endpoint
    base_url = "https://api.hackagent.dev"

    # Output format setup
    console.print("\n[cyan]📊 Output Format Configuration[/cyan]")
    output_format = click.prompt(
        "Default output format",
        type=click.Choice(["table", "json", "csv"]),
        default=cli_config.output_format,
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
    cli_config.api_key = api_key
    cli_config.base_url = base_url
    cli_config.output_format = output_format
    cli_config.verbose = verbose_level

    try:
        cli_config.save()
        console.print("\n[bold green]✅ Configuration saved[/bold green]")

        # Test the configuration
        if cli_config.should_show_info():
            console.print("\n[cyan]🔍 Testing configuration...[/cyan]")
        cli_config.validate()

        # Test API connection
        from hackagent.api.key import key_list
        from hackagent.client import AuthenticatedClient

        client = AuthenticatedClient(
            base_url=cli_config.base_url, token=cli_config.api_key, prefix="Bearer"
        )

        if cli_config.should_show_info():
            with console.status("[bold green]Testing API connection..."):
                response = key_list.sync_detailed(client=client)
        else:
            response = key_list.sync_detailed(client=client)

        if response.status_code == 200:
            console.print(
                "[bold green]✅ Setup complete! API connection verified.[/bold green]"
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

    console.print("[bold cyan]HackAgent CLI v0.2.4[/bold cyan]")
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
            from hackagent.api.agent import agent_list
            from hackagent.client import AuthenticatedClient

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
cli.add_command(results.results)


if __name__ == "__main__":
    cli()
