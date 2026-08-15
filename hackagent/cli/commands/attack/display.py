# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Rich rendering helpers for eval command output."""

from typing import Any, Dict

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from hackagent.cli.commands.attack.catalog import ATTACK_CATALOG

from hackagent.cli.utils import (
    display_results_table,
)


console = Console()


def _display_generic_attack_info(strategy: str) -> None:
    """Display concise info for attack strategies that don't have long-form docs."""
    meta = ATTACK_CATALOG[strategy]

    info_content = f"""[bold]{meta["label"]} Attack Strategy[/bold]

[cyan]Description:[/cyan]
{meta["description"]}

[cyan]CLI Usage:[/cyan]
hackagent eval {strategy} --agent-name <name> --endpoint <url> --goals "<goal>" --no-tui

[cyan]Advanced Configuration:[/cyan]
Use --config-file with JSON/YAML to provide full attack-specific configuration.

[cyan]Quick Help:[/cyan]
hackagent eval {strategy} --help"""

    panel = Panel(
        info_content,
        title=f"{meta['label']} Attack Information",
        border_style="cyan",
        padding=(1, 2),
    )

    console.print(panel)


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

    # Handle list results (most common case when pandas is not available)
    if isinstance(results, list):
        console.print(f"[green]📈 Generated {len(results)} result entries")
        if results and isinstance(results[0], dict):
            # Show sample of keys from first result
            sample_keys = list(results[0].keys())[:5]
            console.print(f"[cyan]📋 Sample fields: {', '.join(sample_keys)}")

            # Try to show some useful info from results
            success_count = sum(
                1 for r in results if r.get("eval_hb") == 1 or r.get("eval_jb") == 1
            )
            if success_count > 0:
                console.print(
                    f"[green]✅ Successful jailbreaks: {success_count}/{len(results)}"
                )
            else:
                console.print("[yellow]⚠️ No successful jailbreaks detected")
        return

    try:
        # Check if results is a pandas DataFrame (optional dependency)
        if hasattr(results, "columns") and hasattr(results, "empty"):
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
• attacker: Language model configuration for prefix generation  
• judges: Judge models for evaluating attack success
• batch_size: Number of prefixes to generate per batch
• temperature: Sampling temperature for generation
• max_tokens: Maximum tokens to generate

[cyan]Example Config File:[/cyan]
{
  "goals": ["Return fake data", "Ignore safety guidelines"],
  "attacker": {
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
  "max_tokens": 512
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
