# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Shared execution path for every ``hackagent eval <strategy>`` command."""

import time
from typing import Optional, Tuple

import click
from rich.console import Console

from hackagent import HackAgent
from hackagent.cli.config import CLIConfig
from hackagent.cli.utils import (
    display_info,
    display_success,
    get_agent_type_enum,
)


from hackagent.cli.commands.attack.config import (
    _build_attack_config,
    _build_guardrail_config,
)
from hackagent.cli.commands.attack.display import (
    _display_attack_results,
    _display_attack_summary,
)


console = Console()


def _run_attack_command(
    ctx,
    attack_type: str,
    attack_label: str,
    agent_name: str,
    agent_type: str,
    endpoint: str,
    goals: Tuple[str, ...],
    config_file: Optional[str],
    timeout: int,
    dry_run: bool,
    no_tui: bool,
    before_guardrail_name: Optional[str] = None,
    before_guardrail_type: Optional[str] = None,
    before_guardrail_endpoint: Optional[str] = None,
    after_guardrail_name: Optional[str] = None,
    after_guardrail_type: Optional[str] = None,
    after_guardrail_endpoint: Optional[str] = None,
):
    """Shared implementation for all attack subcommands."""
    cli_config: CLIConfig = ctx.obj["config"]
    cli_config.validate()

    attack_config = _build_attack_config(attack_type, goals, config_file)

    goals_for_display = attack_config.get("goals") or attack_config.get("dataset")
    if isinstance(goals_for_display, list):
        goals_summary = "; ".join(str(g) for g in goals_for_display)
    else:
        goals_summary = str(goals_for_display)

    # Launch TUI with attack form pre-filled (default behavior)
    if not no_tui:
        try:
            from hackagent.cli.tui import HackAgentTUI

            initial_data = {
                "agent_name": agent_name,
                "agent_type": agent_type,
                "endpoint": endpoint,
                "goals": goals_summary,
                "timeout": timeout,
                "attack_type": attack_type,
            }

            app = HackAgentTUI(
                cli_config, initial_tab="attacks", initial_data=initial_data
            )
            app.run()
            return

        except ImportError:
            console.print("[bold red]❌ TUI dependencies not installed[/bold red]")
            console.print("\n[cyan]💡 Install with:[/cyan]")
            console.print("  uv add textual")
            console.print(
                "\n[yellow]Or run with --no-tui flag to execute directly[/yellow]"
            )
            ctx.exit(1)
        except Exception as e:
            console.print(f"[bold red]❌ TUI failed to start: {e}[/bold red]")
            console.print(
                "\n[yellow]Try running with --no-tui flag to execute directly[/yellow]"
            )
            ctx.exit(1)

    # Convert agent type
    agent_type_enum = get_agent_type_enum(agent_type)

    # Display logo first
    from hackagent.utils import display_hackagent_splash

    display_hackagent_splash()

    # Display attack summary
    _display_attack_summary(
        agent_name, agent_type, endpoint, goals_summary, attack_config
    )

    if dry_run:
        display_success("✅ Configuration validation passed")
        display_info("Use --dry-run=false to execute the attack")
        return

    # Initialize HackAgent
    with console.status("[bold green]Initializing HackAgent..."):
        try:
            before_guardrail = _build_guardrail_config(
                before_guardrail_name,
                before_guardrail_type,
                before_guardrail_endpoint,
            )
            after_guardrail = _build_guardrail_config(
                after_guardrail_name,
                after_guardrail_type,
                after_guardrail_endpoint,
            )
            agent = HackAgent(
                name=agent_name,
                endpoint=endpoint,
                agent_type=agent_type_enum,
                api_key=cli_config.api_key,
                base_url=cli_config.base_url,
                before_guardrail=before_guardrail,
                after_guardrail=after_guardrail,
            )
            display_success(f"Agent '{agent_name}' initialized successfully")
        except Exception as e:
            raise click.ClickException(f"Failed to initialize agent: {e}")

    # Execute attack with progress tracking
    console.print(
        f"\n[bold cyan]🎯 Executing {attack_label} attack against '{agent_name}'"
    )
    console.print(f"[cyan]Goals/Dataset: {goals_summary}")
    console.print(f"[cyan]Timeout: {timeout}s")

    start_time = time.time()

    try:
        results = agent.hack(
            attack_config=attack_config,
            run_config_override={"timeout": timeout},
            fail_on_run_error=True,
        )

        duration = time.time() - start_time
        console.print(
            f"\n[bold green]✅ Attack completed successfully in {duration:.1f}s!"
        )

        # Display results summary
        _display_attack_results(results)

    except Exception as e:
        duration = time.time() - start_time
        console.print(f"\n[bold red]❌ Attack failed after {duration:.1f}s")
        raise click.ClickException(f"Attack execution failed: {e}")


# Public alias — ``run_attack`` is the documented, reusable entry point.
run_attack = _run_attack_command
