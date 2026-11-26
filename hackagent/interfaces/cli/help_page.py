# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Rich-formatted ``hackagent --help`` page for the top-level CLI group."""

import click

from hackagent import resolve_remote_base_url
from hackagent.interfaces.brand import APP, QUICK_START
from hackagent.interfaces.palette import console as themed


def _render_rich_help(ctx: click.Context) -> None:
    """Print the Rich-formatted help page for the main CLI group."""
    from rich.rule import Rule
    from rich.table import Table

    from hackagent.interfaces.cli.banner import splash

    c = themed()

    # ── Logo ──────────────────────────────────────────────────────────────────
    c.print(splash())
    c.print()

    # ── Quick Start ───────────────────────────────────────────────────────────
    # The welcome screen's way through a first campaign, as commands.
    c.print(Rule("[heading]Quick start[/heading]", style="secondary"))
    steps = Table.grid(padding=(0, 3))
    steps.add_column(style="secondary", no_wrap=True)
    steps.add_column(style="accent", no_wrap=True)
    for number, (what, command) in enumerate(QUICK_START, 1):
        steps.add_row(f"  {number}. {what}", command)
    steps.add_row(f"  {APP[0]}", APP[1])
    c.print(steps)
    c.print()

    # ── Commands ──────────────────────────────────────────────────────────────
    c.print(Rule("[heading]Commands[/heading]", style="secondary"))
    cmd_table = Table.grid(padding=(0, 3))
    cmd_table.add_column(style="accent", no_wrap=True, min_width=12)
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
    c.print(Rule("[heading]Options[/heading]", style="secondary"))
    opt_table = Table.grid(padding=(0, 3))
    opt_table.add_column(style="accent", no_wrap=True, min_width=36)
    opt_table.add_column(style="secondary")
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
    c.print(Rule("[heading]Environment variables[/heading]", style="secondary"))
    env_table = Table.grid(padding=(0, 3))
    env_table.add_column(style="accent", no_wrap=True, min_width=24)
    env_table.add_column(style="secondary")
    env_table.add_row("  HACKAGENT_API_KEY", "API key (overrides config file value)")
    env_table.add_row(
        "  HACKAGENT_BASE_URL", f"API base URL (default: {resolve_remote_base_url()})"
    )
    env_table.add_row(
        "  HACKAGENT_DEBUG", "Enable debug output (set to any non-empty value)"
    )
    c.print(env_table)
    c.print()

    # ── Operating Modes ───────────────────────────────────────────────────────
    c.print(Rule("[heading]Where results are kept[/heading]", style="secondary"))
    mode_table = Table.grid(padding=(0, 3))
    mode_table.add_column(no_wrap=True, min_width=10)
    mode_table.add_column(style="secondary")
    mode_table.add_row(
        "  local",
        "No API key needed: results stay in a SQLite database on this machine",
    )
    mode_table.add_row(
        "  remote",
        "With HACKAGENT_API_KEY: results go to the HackAgent platform",
    )
    c.print(mode_table)
    c.print()

    # ── Footer ────────────────────────────────────────────────────────────────
    c.print(Rule(style="secondary"))
    c.print(
        "  [secondary]Docs[/secondary]  [link=https://docs.hackagent.dev]https://docs.hackagent.dev[/link]"
        "    [secondary]API keys[/secondary]  [link=https://app.hackagent.dev]https://app.hackagent.dev[/link]\n"
    )


def _help_option_callback(
    ctx: click.Context, param: click.Parameter, value: bool
) -> None:
    if value and not ctx.resilient_parsing:
        _render_rich_help(ctx)
        ctx.exit()
