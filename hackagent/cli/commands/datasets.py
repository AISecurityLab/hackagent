# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Datasets Commands

Browse built-in dataset presets and sample goals for evals.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import click
from rich.console import Console
from rich.table import Table

from hackagent.cli.utils import display_info, handle_errors
from hackagent.datasets.presets import PRESETS, get_preset

console = Console()

# Fields that are metadata for display, not raw runtime config only.
_DISPLAY_SKIP_KEYS = frozenset({"description"})


@click.group()
def datasets():
    """📚 Browse and sample dataset presets"""
    pass


def _source_for_preset(config: Dict[str, Any]) -> str:
    """Return a short source locator for a preset config."""
    if "path" in config and config["path"]:
        return str(config["path"])
    if "url" in config and config["url"]:
        return str(config["url"])
    return "—"


def _filter_presets(
    provider: Optional[str] = None,
    query: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Return presets filtered by optional provider and name/description query."""
    query_lower = (query or "").strip().lower()
    provider_lower = (provider or "").strip().lower()

    filtered: Dict[str, Dict[str, Any]] = {}
    for name, config in sorted(PRESETS.items()):
        if provider_lower and str(config.get("provider", "")).lower() != provider_lower:
            continue
        if query_lower:
            description = str(config.get("description", "")).lower()
            if query_lower not in name.lower() and query_lower not in description:
                continue
        filtered[name] = config
    return filtered


@datasets.command("list")
@click.option(
    "--provider",
    type=click.Choice(
        ["huggingface", "hf", "file", "local", "url_json"],
        case_sensitive=False,
    ),
    help="Filter by provider type",
)
@click.option(
    "--query",
    "-q",
    help="Filter by name or description substring",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Emit machine-readable JSON",
)
@handle_errors
def list_cmd(provider: Optional[str], query: Optional[str], as_json: bool):
    """List available dataset presets"""

    filtered = _filter_presets(provider=provider, query=query)
    if not filtered:
        display_info("No dataset presets matched the given filters.")
        return

    if as_json:
        payload = [
            {
                "name": name,
                "provider": config.get("provider"),
                "description": config.get("description", ""),
                "source": _source_for_preset(config),
                "goal_field": config.get("goal_field"),
            }
            for name, config in filtered.items()
        ]
        console.print_json(data=payload)
        return

    table = Table(
        title=f"Dataset Presets ({len(filtered)})",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Provider", style="green")
    table.add_column("Source", style="dim", overflow="fold")
    table.add_column("Description", overflow="fold")

    for name, config in filtered.items():
        table.add_row(
            name,
            str(config.get("provider", "—")),
            _source_for_preset(config),
            str(config.get("description", "No description")),
        )

    console.print(table)
    console.print(
        "\n[dim]Tip:[/dim] use [cyan]hackagent datasets show <name>[/cyan] "
        "or [cyan]hackagent datasets sample <name>[/cyan]"
    )


@datasets.command("show")
@click.argument("preset")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Emit machine-readable JSON",
)
@handle_errors
def show_cmd(preset: str, as_json: bool):
    """Show details for a dataset preset"""

    config = get_preset(preset)

    if as_json:
        console.print_json(data={"name": preset.lower().replace("-", "_"), **config})
        return

    table = Table(
        title=f"Dataset Preset: {preset}",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green", overflow="fold")

    description = config.get("description", "No description")
    table.add_row("Description", str(description))

    for key, value in config.items():
        if key in _DISPLAY_SKIP_KEYS:
            continue
        if isinstance(value, (list, dict)):
            rendered = json.dumps(value, indent=2)
        else:
            rendered = str(value)
        table.add_row(key, rendered)

    console.print(table)
    console.print(
        f"\n[dim]Sample goals:[/dim] [cyan]hackagent datasets sample {preset} --limit 5[/cyan]"
    )


@datasets.command("sample")
@click.argument("preset")
@click.option("--limit", default=5, show_default=True, help="Number of goals to load")
@click.option("--shuffle", is_flag=True, help="Shuffle before selecting")
@click.option("--seed", type=int, help="Random seed used with --shuffle")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Emit machine-readable JSON",
)
@handle_errors
def sample_cmd(
    preset: str,
    limit: int,
    shuffle: bool,
    seed: Optional[int],
    as_json: bool,
):
    """Load and print sample goals from a dataset preset"""

    if limit < 1:
        raise click.ClickException("--limit must be at least 1")

    # Validate preset early for a clear error before network I/O.
    get_preset(preset)

    from hackagent.datasets import load_goals

    with console.status(f"[bold green]Loading up to {limit} goals from '{preset}'..."):
        goals: List[str] = load_goals(
            preset=preset,
            limit=limit,
            shuffle=shuffle,
            seed=seed,
        )

    if not goals:
        display_info(f"No goals returned for preset '{preset}'.")
        return

    if as_json:
        console.print_json(
            data={
                "preset": preset,
                "count": len(goals),
                "goals": goals,
            }
        )
        return

    console.print(
        f"[bold cyan]Sample goals from '{preset}'[/bold cyan] "
        f"[dim]({len(goals)} shown)[/dim]\n"
    )
    for index, goal in enumerate(goals, start=1):
        console.print(f"[cyan]{index}.[/cyan] {goal}")

    console.print(
        f"\n[dim]Use in evals:[/dim] "
        f"[cyan]hackagent eval advprefix --dataset {preset} --limit {limit} ...[/cyan]"
    )
