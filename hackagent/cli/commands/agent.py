"""
Agent Commands

Manage AI agents registered with HackAgent.
"""

import click

from hackagent.cli.config import CLIConfig
from hackagent.cli.utils import handle_errors, launch_tui


@click.group()
def agent():
    """🤖 Manage AI agents"""
    pass


@agent.command()
@click.pass_context
@handle_errors
def list(ctx):
    """List registered agents"""
    cli_config: CLIConfig = ctx.obj["config"]
    cli_config.validate()
    launch_tui(cli_config, initial_tab="agents")


@agent.command()
@click.option("--name", required=True, help="Agent name")
@click.option(
    "--type",
    "agent_type",
    type=click.Choice(["google-adk", "litellm"]),
    required=True,
    help="Agent type",
)
@click.option("--endpoint", required=True, help="Agent endpoint URL")
@click.option("--description", help="Agent description")
@click.option("--metadata", help="Additional metadata as JSON string")
@click.pass_context
@handle_errors
def create(ctx, name, agent_type, endpoint, description, metadata):
    """Create a new agent"""
    cli_config: CLIConfig = ctx.obj["config"]
    cli_config.validate()
    launch_tui(cli_config, initial_tab="agents")


@agent.command()
@click.argument("agent_id")
@click.pass_context
@handle_errors
def show(ctx, agent_id):
    """Show detailed information about an agent"""
    cli_config: CLIConfig = ctx.obj["config"]
    cli_config.validate()
    launch_tui(cli_config, initial_tab="agents")


@agent.command()
@click.argument("agent_id")
@click.option("--name", help="New agent name")
@click.option("--endpoint", help="New agent endpoint")
@click.option("--description", help="New agent description")
@click.option("--metadata", help="New metadata as JSON string")
@click.pass_context
@handle_errors
def update(ctx, agent_id, name, endpoint, description, metadata):
    """Update an existing agent"""
    cli_config: CLIConfig = ctx.obj["config"]
    cli_config.validate()
    launch_tui(cli_config, initial_tab="agents")


@agent.command()
@click.argument("agent_id")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
@handle_errors
def delete(ctx, agent_id, confirm):
    """Delete an agent"""
    cli_config: CLIConfig = ctx.obj["config"]
    cli_config.validate()
    launch_tui(cli_config, initial_tab="agents")


@agent.command()
@click.argument("agent_name")
@click.pass_context
@handle_errors
def test(ctx, agent_name):
    """Test connection to an agent

    This command attempts to establish a connection with the specified agent
    to verify it's accessible and responding.
    """
    cli_config: CLIConfig = ctx.obj["config"]
    cli_config.validate()
    launch_tui(cli_config, initial_tab="agents")
