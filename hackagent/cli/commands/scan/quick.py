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

from hackagent import HackAgent
from hackagent.cli.config import CLIConfig
from hackagent.cli.utils import (
    display_info,
    display_success,
    get_agent_type_enum,
)

from hackagent.cli.commands.scan.helpers import (
    _extract_asr,
    _format_asr,
    _normalize_attack_type,
)

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

    from hackagent.risks.jailbreak import JAILBREAK_PROFILE
    from hackagent.utils import display_hackagent_splash

    primary_attacks = [rec.technique for rec in JAILBREAK_PROFILE.primary_attacks]
    if not primary_attacks:
        raise click.ClickException("No primary attacks defined in JAILBREAK_PROFILE.")

    if dataset_preset:
        chosen_dataset = dataset_preset
    else:
        if not JAILBREAK_PROFILE.primary_datasets:
            raise click.ClickException(
                "No primary datasets defined in JAILBREAK_PROFILE. Please provide --dataset."
            )
        chosen_dataset = JAILBREAK_PROFILE.primary_datasets[0].preset

    display_hackagent_splash()

    summary = Panel(
        (
            f"[bold]Target Agent:[/bold] {agent_name}\n"
            f"[bold]Agent Type:[/bold] {agent_type}\n"
            f"[bold]Endpoint:[/bold] {endpoint}\n"
            f"[bold]Dataset:[/bold] {chosen_dataset} (limit={limit})\n"
            f"[bold]Attacks:[/bold] {', '.join(primary_attacks)}\n"
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

    agent_type_enum = get_agent_type_enum(agent_type)

    with console.status("[bold green]Initializing HackAgent..."):
        agent = HackAgent(
            name=agent_name,
            endpoint=endpoint,
            agent_type=agent_type_enum,
            api_key=cli_config.api_key,
            base_url=cli_config.base_url,
        )

    rows: list[Tuple[str, str, str, str, str, str]] = []
    failed_attacks = 0

    for technique in primary_attacks:
        attack_type = _normalize_attack_type(technique)
        display_info(f"Running {technique}...")

        attack_config: Dict[str, Any] = {
            "attack_type": attack_type,
            "dataset": {"preset": chosen_dataset, "limit": limit},
            "judges": [{"identifier": judge_identifier, "type": judge_type}],
        }

        attack_start = time.time()
        try:
            result = agent.hack(
                attack_config=attack_config,
                run_config_override={"timeout": timeout},
                fail_on_run_error=True,
            )
            duration = time.time() - attack_start

            asr = _extract_asr(result)
            result_count = (
                len(result)
                if isinstance(result, list)
                else (len(result) if hasattr(result, "__len__") else 1)
            )

            rows.append(
                (
                    technique,
                    "✅ OK",
                    str(result_count),
                    _format_asr(asr),
                    f"{duration:.1f}s",
                    "-",
                )
            )

        except (
            Exception
        ) as exc:  # pragma: no cover - wrapped by handle_errors in CLI flow
            duration = time.time() - attack_start
            failed_attacks += 1
            rows.append(
                (
                    technique,
                    "❌ FAILED",
                    "0",
                    "N/A",
                    f"{duration:.1f}s",
                    str(exc),
                )
            )

            if fail_fast:
                break

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

    if failed_attacks > 0:
        raise click.ClickException(
            f"Evaluation campaign completed with {failed_attacks} failed attack(s)."
        )

    display_success("Evaluation campaign completed successfully.")
