# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The ``hackagent eval list`` and ``hackagent eval info`` commands."""

import click
from rich.console import Console
from rich.table import Table

from hackagent.interfaces.cli.utils import (
    handle_errors,
)


from hackagent.client import catalog_by_id, grouped_catalog
from hackagent.interfaces.cli.commands.attack.display import (
    _display_advprefix_info,
    _display_generic_attack_info,
)
from hackagent.interfaces.cli.commands.attack.group import eval_cmd


console = Console()


@eval_cmd.command(name="list")
@click.pass_context
@handle_errors
def list_attacks(ctx):
    """List available attack strategies, grouped by primary category"""

    table = Table(
        title="Available Attack Strategies", show_header=True, header_style="bold cyan"
    )
    table.add_column("Strategy", style="cyan")
    table.add_column("Category", style="magenta")
    table.add_column("Tags", style="blue")
    table.add_column("Description", style="green")
    table.add_column("Status", style="yellow")

    for _category, _label, entries in grouped_catalog():
        for meta in entries:
            tags = ", ".join(meta["tags"]) if meta["tags"] else "—"
            table.add_row(
                meta["attack_type"],
                meta["category_label"],
                tags,
                meta["description"],
                "✅ Available",
            )

    console.print(table)
    console.print(
        "\n[dim]Primary category is how the target is hit: Static (fixed "
        "transforms), Adaptive (independent refine/search), or Multi-turn "
        "(one growing conversation). Tags such as multimodal or RAG/indirect "
        "are secondary.[/dim]"
    )
    console.print(
        "\n[cyan]💡 Use 'hackagent eval STRATEGY --help' for strategy-specific options"
    )


@eval_cmd.command()
@click.argument("strategy", type=click.Choice(list(catalog_by_id())))
@click.pass_context
@handle_errors
def info(ctx, strategy):
    """Get detailed information about an attack strategy"""

    if strategy == "advprefix":
        _display_advprefix_info()
    else:
        _display_generic_attack_info(strategy)
