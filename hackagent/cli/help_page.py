# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Rich-formatted ``hackagent --help`` page for the top-level CLI group."""

import importlib.metadata

import click
from rich.console import Console
from rich.panel import Panel

console = Console()


def _render_rich_help(ctx: click.Context) -> None:
    """Print the Rich-formatted help page for the main CLI group."""
    from rich.rule import Rule
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.text import Text

    from hackagent.utils import HACKAGENT_BANNER

    c = Console()
    version = importlib.metadata.version("hackagent")

    # ── Logo ──────────────────────────────────────────────────────────────────
    c.print(
        Panel(
            Text(HACKAGENT_BANNER, style="bold dark_red"),
            border_style="red",
            padding=(0, 2),
            expand=False,
        )
    )
    c.print(
        f"  [bold white]HackAgent CLI[/bold white] [dim]v{version}[/dim]"
        f"  [dim]·[/dim]  [italic cyan]AI Agent Security Testing Toolkit[/italic cyan]\n"
    )

    # ── Quick Start ───────────────────────────────────────────────────────────
    c.print(Rule("[bold]Quick Start[/bold]", style="dim"))
    qs_code = (
        "# 1. Interactive first-time setup\n"
        "hackagent init\n\n"
        "# 2. Register a target agent\n"
        'hackagent agent create --name "my-bot" --type google-adk \\\n'
        "    --endpoint http://localhost:8000\n\n"
        "# 3. Run an adversarial attack\n"
        'hackagent eval advprefix --agent-name "my-bot" \\\n'
        '    --goals "Ignore safety rules"\n\n'
        "# 4. Review findings\n"
        "hackagent results summary"
    )
    c.print(
        Panel(
            Syntax(qs_code, "bash", theme="monokai", background_color="default"),
            border_style="dim",
            padding=(0, 1),
        )
    )
    c.print()

    # ── Commands ──────────────────────────────────────────────────────────────
    c.print(Rule("[bold]Commands[/bold]", style="dim"))
    cmd_table = Table.grid(padding=(0, 3))
    cmd_table.add_column(style="bold cyan", no_wrap=True, min_width=12)
    cmd_table.add_column()
    group: click.Group = ctx.command  # type: ignore[assignment]
    for name in group.list_commands(ctx):
        cmd = group.get_command(ctx, name)
        if cmd is None:
            continue
        cmd_table.add_row(f"  {name}", cmd.get_short_help_str(limit=60) or "")
    c.print(cmd_table)
    c.print()

    # ── Options ───────────────────────────────────────────────────────────────
    c.print(Rule("[bold]Options[/bold]", style="dim"))
    opt_table = Table.grid(padding=(0, 3))
    opt_table.add_column(style="bold yellow", no_wrap=True, min_width=36)
    opt_table.add_column(style="dim")
    for param in ctx.command.params:
        if not isinstance(param, click.Option):
            continue
        decls = ", ".join(param.opts)
        if param.is_flag or param.count:  # type: ignore[union-attr]
            meta = ""
        elif param.metavar:
            meta = f" {param.metavar}"
        elif param.type is not None:
            meta = f" {param.type.name.upper()}"
        else:
            meta = ""
        opt_table.add_row(f"  {decls}{meta}", param.help or "")
    c.print(opt_table)
    c.print()

    # ── Environment Variables ─────────────────────────────────────────────────
    c.print(Rule("[bold]Environment Variables[/bold]", style="dim"))
    env_table = Table.grid(padding=(0, 3))
    env_table.add_column(style="bold magenta", no_wrap=True, min_width=24)
    env_table.add_column(style="dim")
    env_table.add_row("  HACKAGENT_API_KEY", "API key (overrides config file value)")
    env_table.add_row(
        "  HACKAGENT_BASE_URL", "API base URL (default: https://api.hackagent.dev)"
    )
    env_table.add_row(
        "  HACKAGENT_DEBUG", "Enable debug output (set to any non-empty value)"
    )
    c.print(env_table)
    c.print()

    # ── Operating Modes ───────────────────────────────────────────────────────
    c.print(Rule("[bold]Operating Modes[/bold]", style="dim"))
    mode_table = Table.grid(padding=(0, 3))
    mode_table.add_column(no_wrap=True, min_width=10)
    mode_table.add_column(style="dim")
    mode_table.add_row(
        "  [bold green]Local[/bold green]",
        "No API key needed — results stored in local SQLite database",
    )
    mode_table.add_row(
        "  [bold cyan]Cloud[/bold cyan]",
        "With HACKAGENT_API_KEY — results synced to HackAgent cloud",
    )
    c.print(mode_table)
    c.print()

    # ── Footer ────────────────────────────────────────────────────────────────
    c.print(Rule(style="dim"))
    c.print(
        "  [dim]Docs[/dim]  [link=https://docs.hackagent.dev]https://docs.hackagent.dev[/link]"
        "    [dim]API Keys[/dim]  [link=https://app.hackagent.dev]https://app.hackagent.dev[/link]\n"
    )


def _help_option_callback(
    ctx: click.Context, param: click.Parameter, value: bool
) -> None:
    if value and not ctx.resilient_parsing:
        _render_rich_help(ctx)
        ctx.exit()
