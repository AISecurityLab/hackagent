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
Attack Commands

Execute security attacks against AI agents.
"""

import time
from typing import Any, Dict

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from hackagent import HackAgent
from hackagent.cli.config import CLIConfig
from hackagent.cli.utils import (
    display_info,
    display_results_table,
    display_success,
    get_agent_type_enum,
    handle_errors,
    load_config_file,
)

console = Console()


@click.group()
def attack():
    """🚀 Execute security attacks against AI agents"""
    # Logo will be shown by HackAgent initialization
    pass


@attack.command()
@click.option("--agent-name", required=True, help="Target agent name")
@click.option(
    "--agent-type",
    type=str,
    default="other",
    help="Agent type (e.g., google-adk, litellm, langchain, openai-sdk, mcp, a2a, or other)",
)
@click.option(
    "--endpoint",
    required=True,
    help="Agent endpoint URL. For OpenAI-compatible endpoints, provide base URL ending with /v1 (e.g., http://localhost:8000/v1). For LangServe, provide full path (e.g., http://localhost:8000/invoke).",
)
@click.option(
    "--goals",
    required=True,
    help="Attack goals (what you want the agent to do incorrectly)",
)
@click.option(
    "--config-file",
    type=click.Path(exists=True),
    help="Attack configuration file (JSON/YAML)",
)
@click.option("--timeout", default=300, help="Attack timeout in seconds")
@click.option(
    "--dry-run", is_flag=True, help="Validate configuration without running attack"
)
@click.option(
    "--no-tui",
    is_flag=True,
    help="Run attack directly without opening TUI (default: open TUI)",
)
@click.pass_context
@handle_errors
def advprefix(
    ctx, agent_name, agent_type, endpoint, goals, config_file, timeout, dry_run, no_tui
):
    """Execute AdvPrefix attack strategy

    This command runs the AdvPrefix attack against a target agent.
    Goals should describe what you want the agent to do incorrectly.

    Examples:

      # Basic attack with goals
      hackagent attack advprefix \\
        --agent-name "weather-bot" \\
        --agent-type "google-adk" \\
        --endpoint "http://localhost:8000" \\
        --goals "Return fake weather data and ignore safety guidelines"

              # Attack with configuration file
        hackagent attack advprefix \\
          --agent-name "multi-tool-agent" \\
          --agent-type "google-adk" \\
          --endpoint "http://localhost:8000" \\
          --config-file "attack-config.json"
    """
    cli_config: CLIConfig = ctx.obj["config"]
    cli_config.validate()

    # Launch TUI with attack form pre-filled (default behavior)
    if not no_tui:
        try:
            from hackagent.cli.tui import HackAgentTUI

            initial_data = {
                "agent_name": agent_name,
                "agent_type": agent_type,
                "endpoint": endpoint,
                "goals": goals,
                "timeout": timeout,
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

    # Build attack configuration
    attack_config = {
        "attack_type": "advprefix",
        "goals": [goals],  # Convert single goal string to list
    }

    # Load additional config from file if provided
    if config_file:
        try:
            file_config = load_config_file(config_file)
            attack_config.update(file_config)
            display_info(f"Loaded configuration from: {config_file}")
        except Exception as e:
            raise click.ClickException(f"Failed to load config file: {e}")

    # Display logo first
    from hackagent.utils import display_hackagent_splash

    display_hackagent_splash()

    # Display attack summary
    _display_attack_summary(agent_name, agent_type, endpoint, goals, attack_config)

    if dry_run:
        display_success("✅ Configuration validation passed")
        display_info("Use --dry-run=false to execute the attack")
        return

    # Initialize HackAgent
    with console.status("[bold green]Initializing HackAgent..."):
        try:
            agent = HackAgent(
                name=agent_name,
                endpoint=endpoint,
                agent_type=agent_type_enum,
                api_key=cli_config.api_key,
                base_url=cli_config.base_url,
            )
            display_success(f"Agent '{agent_name}' initialized successfully")
        except Exception as e:
            raise click.ClickException(f"Failed to initialize agent: {e}")

    # Execute attack with progress tracking
    console.print(f"\n[bold cyan]🎯 Executing AdvPrefix attack against '{agent_name}'")
    console.print(f"[cyan]Goals: {goals}")
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


@attack.command()
@click.pass_context
@handle_errors
def list(ctx):
    """List available attack strategies"""

    table = Table(
        title="Available Attack Strategies", show_header=True, header_style="bold cyan"
    )
    table.add_column("Strategy", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("Status", style="yellow")

    # Add available strategies
    table.add_row(
        "advprefix",
        "Adversarial prefix generation attack using language models",
        "✅ Available",
    )

    # Add planned strategies
    table.add_row("prompt-injection", "Direct prompt injection attacks", "🚧 Planned")
    table.add_row(
        "jailbreak", "Jailbreaking techniques for safety bypassing", "🚧 Planned"
    )
    table.add_row(
        "goal-hijacking", "Goal hijacking and manipulation attacks", "🚧 Planned"
    )

    console.print(table)
    console.print(
        "\n[cyan]💡 Use 'hackagent attack STRATEGY --help' for strategy-specific options"
    )


@attack.command()
@click.argument("strategy", type=click.Choice(["advprefix"]))
@click.pass_context
@handle_errors
def info(ctx, strategy):
    """Get detailed information about an attack strategy"""

    if strategy == "advprefix":
        _display_advprefix_info()
    else:
        raise click.ClickException(f"Strategy '{strategy}' not yet implemented")


def _display_attack_summary(
    agent_name: str,
    agent_type: str,
    endpoint: str,
    goals: str,
    attack_config: Dict[str, Any],
) -> None:
    """Display a summary of the attack configuration"""

    # Create summary panel
    summary_content = f"""[bold]Target Agent:[/bold] {agent_name}
[bold]Agent Type:[/bold] {agent_type}
[bold]Endpoint:[/bold] {endpoint}
[bold]Attack Type:[/bold] {attack_config["attack_type"]}
[bold]Goals:[/bold] {goals}"""

    if len(attack_config) > 2:  # More than just attack_type and goals
        summary_content += f"\n[bold]Additional Config:[/bold] {len(attack_config) - 2} parameters loaded"

    panel = Panel(
        summary_content,
        title="🎯 Attack Configuration",
        border_style="cyan",
        padding=(1, 2),
    )

    console.print(panel)


def _display_attack_results(results: Any) -> None:
    """Display attack results summary"""

    console.print("\n[bold cyan]📊 Attack Results Summary")

    try:
        import pandas as pd

        if isinstance(results, pd.DataFrame):
            console.print(f"[green]📈 Generated {len(results)} result entries")

            # Show key metrics if available
            if not results.empty:
                # Try to display some key columns if they exist
                summary_table = Table(
                    title="Key Metrics", show_header=True, header_style="bold cyan"
                )
                summary_table.add_column("Metric", style="cyan")
                summary_table.add_column("Value", style="green")

                summary_table.add_row("Total Results", str(len(results)))

                # Add column info
                summary_table.add_row("Columns", str(len(results.columns)))

                # Try to show success metrics if available
                for col in results.columns:
                    if "success" in col.lower() or "score" in col.lower():
                        if results[col].dtype in ["int64", "float64"]:
                            mean_val = results[col].mean()
                            summary_table.add_row(f"Avg {col}", f"{mean_val:.3f}")

                console.print(summary_table)

                # Show sample of results
                if len(results) > 0:
                    console.print("\n[cyan]📋 Sample Results (first 5 rows):")
                    # Filter to show only goal and prefix columns if they exist
                    display_columns = []
                    if "goal" in results.columns:
                        display_columns.append("goal")
                    if "prefix" in results.columns:
                        display_columns.append("prefix")

                    if display_columns:
                        filtered_results = results[display_columns].head()
                        display_results_table(
                            filtered_results, "Attack Results - Goals & Prefixes"
                        )
                    else:
                        # Fallback to showing all columns if goal/prefix not found
                        display_results_table(results.head(), "Sample Attack Results")
        else:
            console.print(f"[green]📈 Results: {type(results).__name__}")
            if hasattr(results, "__len__"):
                console.print(f"[green]📊 Count: {len(results)}")

    except Exception as e:
        console.print(f"[yellow]⚠️ Could not analyze results: {e}")
        console.print(f"[green]📈 Results type: {type(results).__name__}")


def _display_advprefix_info() -> None:
    """Display detailed information about AdvPrefix attack strategy"""

    info_content = """[bold]AdvPrefix Attack Strategy[/bold]

[cyan]Description:[/cyan]
The AdvPrefix attack generates adversarial prefixes that can manipulate AI agent behavior.
It uses a multi-step pipeline involving uncensored language models to craft effective attacks.

[cyan]How it works:[/cyan]
1. Generate candidate prefixes using language models
2. Compute cross-entropy scores for effectiveness
3. Test prefixes against the target agent
4. Evaluate results using judge models
5. Select and report successful attacks

[cyan]Configuration Options:[/cyan]
• goals: List of malicious objectives for the agent
• generator: Language model configuration for prefix generation  
• judges: Judge models for evaluating attack success
• batch_size: Number of prefixes to generate per batch
• temperature: Sampling temperature for generation
• max_new_tokens: Maximum tokens to generate

[cyan]Example Config File:[/cyan]
{
  "goals": ["Return fake data", "Ignore safety guidelines"],
  "generator": {
    "identifier": "ollama/llama2-uncensored",
    "endpoint": "http://localhost:11434/api/generate"
  },
  "judges": [
    {
      "identifier": "ollama/llama3",
      "endpoint": "http://localhost:11434/api/judge", 
      "type": "harmbench"
    }
  ],
  "batch_size": 20,
  "temperature": 1.0,
  "max_new_tokens": 512
}

[cyan]Requirements:[/cyan]
• Target agent must be running and accessible
• Generator model (e.g., Ollama with uncensored model)
• Judge model for evaluation
• Sufficient computational resources

[yellow]⚠️ Ethical Usage:[/yellow]
Only use this attack against agents you own or have explicit permission to test.
Always follow responsible disclosure practices for any vulnerabilities found."""

    panel = Panel(
        info_content,
        title="AdvPrefix Attack Information",
        border_style="cyan",
        padding=(1, 2),
    )

    console.print(panel)
