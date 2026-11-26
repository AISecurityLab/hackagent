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
from rich.table import Table

from hackagent.client import load_goals, preset as get_preset, presets
from hackagent.interfaces.cli.utils import (
    Failed,
    console,
    display_heading,
    display_hint,
    display_info,
    handle_errors,
)

# Fields that are metadata for display, not raw runtime config only.
_DISPLAY_SKIP_KEYS = frozenset({"description"})


@click.group()
def datasets():
    """Browse and sample dataset presets."""


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
    for name, config in sorted(presets().items()):
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
        header_style="heading",
    )
    table.add_column("Name", style="name", no_wrap=True)
    table.add_column("Provider")
    table.add_column("Source", style="secondary", overflow="fold")
    table.add_column("Description", overflow="fold")

    for name, config in filtered.items():
        table.add_row(
            name,
            str(config.get("provider", "—")),
            _source_for_preset(config),
            str(config.get("description", "No description")),
        )

    console.print(table)
    console.print()
    display_hint("About one", "hackagent datasets show NAME")
    display_hint("Some of its goals", "hackagent datasets sample NAME")


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
        header_style="heading",
    )
    table.add_column("Property", style="accent")
    table.add_column("Value", overflow="fold")

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
    console.print()
    display_hint("Some of its goals", f"hackagent datasets sample {preset} --limit 5")


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
        raise Failed("--limit must be at least 1")

    # Validate preset early for a clear error before network I/O.
    get_preset(preset)

    with console.status(f"Loading up to {limit} goals from '{preset}'…"):
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

    display_heading(f"Goals from {preset} [secondary]({len(goals)} shown)[/secondary]")
    listed = Table.grid(padding=(0, 1))
    listed.add_column(style="secondary", justify="right", no_wrap=True)
    listed.add_column()
    for index, goal in enumerate(goals, start=1):
        listed.add_row(f"{index}.", goal)
    console.print(listed)

    console.print()
    display_hint(
        "In a campaign", f"dataset: {{source: {{type: preset, name: {preset}}}}}"
    )
