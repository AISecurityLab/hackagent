# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The ``hackagent eval list`` and ``hackagent eval info`` commands."""

import click
from rich.console import Console
from rich.table import Table

from hackagent.cli.utils import (
    handle_errors,
)


from hackagent.attacks.taxonomy import (
    AttackCategory,
    get_attack_taxonomy,
    grouped_attack_keys,
)
from hackagent.cli.commands.attack.catalog import ATTACK_CATALOG
from hackagent.cli.commands.attack.display import (
    _display_advprefix_info,
    _display_generic_attack_info,
)
from hackagent.cli.commands.attack.group import eval_cmd


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

    grouped = grouped_attack_keys(ATTACK_CATALOG.keys())
    for category in AttackCategory:
        for attack_key in grouped[category]:
            meta = ATTACK_CATALOG[attack_key]
            tax = get_attack_taxonomy(attack_key)
            tags = ", ".join(tag.value for tag in tax.tags) if tax.tags else "—"
            table.add_row(
                attack_key,
                tax.category.label,
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
@click.argument("strategy", type=click.Choice(list(ATTACK_CATALOG.keys())))
@click.pass_context
@handle_errors
def info(ctx, strategy):
    """Get detailed information about an attack strategy"""

    if strategy == "advprefix":
        _display_advprefix_info()
    else:
        _display_generic_attack_info(strategy)
