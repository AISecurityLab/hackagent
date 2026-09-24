# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""``run_quick_scan``: the canned jailbreak campaign behind ``hackagent eval``."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from hackagent import AgentType, HackAgent, Settings
from hackagent.client import primary_attacks, primary_dataset
from hackagent.interfaces.cli.config import CLIConfig
from hackagent.interfaces.cli.utils import (
    display_info,
    display_success,
)

from hackagent.interfaces.cli.commands.scan.helpers import _extract_asr, _format_asr

console = Console()


def run_quick_scan(
    ctx: click.Context,
    agent_name: str,
    agent_type: str,
    endpoint: str,
    dataset_preset: Optional[str],
    limit: int,
    judge_identifier: str,
    judge_type: str,
    timeout: int,
    fail_fast: bool,
    dry_run: bool,
) -> None:
    """Run the quick 3-attack security scan implementation."""
    cli_config: CLIConfig = ctx.obj["config"]
    cli_config.validate()

    from hackagent.interfaces.cli.banner import display_hackagent_splash

    campaign = primary_attacks()
    if not campaign:
        raise click.ClickException("No primary attacks are defined for the campaign.")

    if dataset_preset:
        chosen_dataset = dataset_preset
    else:
        chosen_dataset = primary_dataset()
        if not chosen_dataset:
            raise click.ClickException(
                "No primary dataset is defined. Please provide --dataset."
            )

    display_hackagent_splash()

    summary = Panel(
        (
            f"[bold]Target Agent:[/bold] {agent_name}\n"
            f"[bold]Agent Type:[/bold] {agent_type}\n"
            f"[bold]Endpoint:[/bold] {endpoint}\n"
            f"[bold]Dataset:[/bold] {chosen_dataset} (limit={limit})\n"
            f"[bold]Attacks:[/bold] {', '.join(campaign)}\n"
            f"[bold]Judge:[/bold] {judge_identifier} ({judge_type})\n"
            f"[bold]Timeout:[/bold] {timeout}s"
        ),
        title="⚡ Quick Security Scan Plan",
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(summary)

    if dry_run:
        display_success("Dry run completed. Configuration is valid.")
        return

    agent_type_enum = AgentType.parse(agent_type)

    with console.status("[bold green]Initializing HackAgent..."):
        session = HackAgent(
            Settings.resolve(
                api_key=cli_config.api_key or "",
                base_url=cli_config.base_url,
            )
        )
        agent = session.target(endpoint, agent_type_enum, name=agent_name)

    attacks: list[Dict[str, Any]] = []
    for index, technique in enumerate(campaign):
        step: Dict[str, Any] = {
            "attack_type": technique,
            "judges": [{"identifier": judge_identifier, "type": judge_type}],
        }
        if index == 0:
            step["dataset"] = {"preset": chosen_dataset, "limit": limit}
        attacks.append(step)

    display_info("Running jailbreak chain...")
    attack_start = time.time()
    try:
        result = agent.hack_chain(
            attacks=attacks,
            run_config_override={"timeout": timeout},
            fail_on_run_error=fail_fast,
        )
    except Exception as exc:  # pragma: no cover - wrapped for the CLI
        duration = time.time() - attack_start
        rows = [
            (
                ", ".join(campaign),
                "❌ FAILED",
                "0",
                "N/A",
                f"{duration:.1f}s",
                str(exc),
            )
        ]
        _print_quick_scan_table(rows)
        raise click.ClickException(
            "Evaluation campaign completed with 1 failed attack(s)."
        ) from exc

    duration = time.time() - attack_start
    grouped: Dict[str, list] = {technique: [] for technique in campaign}
    if isinstance(result, list):
        for row in result:
            if isinstance(row, dict):
                key = str(row.get("chain_attack_type") or campaign[0])
                grouped.setdefault(key, []).append(row)
    rows = []
    for technique in campaign:
        technique_rows = grouped.get(technique, [])
        rows.append(
            (
                technique,
                "✅ OK" if technique_rows or not result else "—",
                str(len(technique_rows)),
                _format_asr(_extract_asr(technique_rows or result)),
                f"{duration:.1f}s",
                "-",
            )
        )

    _print_quick_scan_table(rows)
    display_success("Evaluation campaign completed successfully.")


def _print_quick_scan_table(rows: list[Tuple[str, str, str, str, str, str]]) -> None:
    table = Table(
        title="Quick Security Scan Results",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Attack", style="cyan")
    table.add_column("Status")
    table.add_column("Results")
    table.add_column("ASR")
    table.add_column("Duration")
    table.add_column("Notes", overflow="fold")

    for row in rows:
        table.add_row(*row)

    console.print()
    console.print(table)
