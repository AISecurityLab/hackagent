# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The ``hackagent eval list`` and ``hackagent eval info`` commands."""

import click
from rich.console import Console
from rich.table import Table

from hackagent.cli.utils import (
    handle_errors,
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
    """List available attack strategies"""

    table = Table(
        title="Available Attack Strategies", show_header=True, header_style="bold cyan"
    )
    table.add_column("Strategy", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("Status", style="yellow")

    for attack_key, meta in ATTACK_CATALOG.items():
        table.add_row(attack_key, meta["description"], "✅ Available")

    console.print(table)
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
