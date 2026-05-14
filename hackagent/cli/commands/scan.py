# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Quick security scan implementation.

Runs the Jailbreak evaluation campaign using primary attacks from JAILBREAK_PROFILE.

Also exposes reusable `run_quick_scan` for the unified `hackagent eval` flow.
"""

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
    handle_errors,
)

console = Console()


def _normalize_attack_type(technique: str) -> str:
    """Convert profile technique labels to CLI/runtime attack_type keys."""
    return str(technique).strip().lower()


def _extract_asr(results: Any) -> Optional[float]:
    """Extract a best-effort ASR value from dict/list/dataframe-like results."""
    if isinstance(results, dict):
        asr = results.get("asr")
        if isinstance(asr, (int, float)):
            return float(asr)
        return None

    # Pandas-like path (without importing pandas explicitly)
    if hasattr(results, "columns") and hasattr(results, "__len__"):
        try:
            columns = set(results.columns)
            if "asr" in columns:
                series = results["asr"]
                if hasattr(series, "mean"):
                    mean_val = series.mean()
                    if isinstance(mean_val, (int, float)):
                        return float(mean_val)
        except Exception:
            return None

    if isinstance(results, list) and results and isinstance(results[0], dict):
        numeric_asr = [
            r.get("asr") for r in results if isinstance(r.get("asr"), (int, float))
        ]
        if numeric_asr:
            return float(sum(numeric_asr) / len(numeric_asr))

        # Fallback for per-goal boolean/numeric success traces
        success_keys = ("is_success", "success", "eval_jb", "eval_hb")
        success_values = []
        for row in results:
            for key in success_keys:
                value = row.get(key)
                if isinstance(value, bool):
                    success_values.append(1.0 if value else 0.0)
                    break
                if isinstance(value, (int, float)):
                    success_values.append(float(value))
                    break

        if success_values:
            return float(sum(success_values) / len(success_values))

    return None


def _format_asr(asr: Optional[float]) -> str:
    """Render ASR as human-readable percentage."""
    if asr is None:
        return "N/A"

    pct = asr * 100.0 if 0.0 <= asr <= 1.0 else asr
    return f"{pct:.1f}%"


@click.command("scan")
@click.option("--agent-name", required=True, help="Target agent name")
@click.option(
    "--agent-type",
    type=str,
    default="other",
    show_default=True,
    help="Agent type (e.g., google-adk, litellm, langchain, openai-sdk, mcp, a2a, or other)",
)
@click.option(
    "--endpoint",
    required=True,
    help="Agent endpoint URL. For OpenAI-compatible endpoints, use a base URL ending with /v1.",
)
@click.option(
    "--dataset",
    "dataset_preset",
    default=None,
    help="Dataset preset for the evaluation campaign (default: first PRIMARY dataset in JAILBREAK_PROFILE).",
)
@click.option(
    "--limit",
    type=int,
    default=25,
    show_default=True,
    help="Maximum number of goals loaded from the dataset per attack.",
)
@click.option(
    "--judge-identifier",
    default="ollama/llama3",
    show_default=True,
    help="Judge model identifier.",
)
@click.option(
    "--judge-type",
    default="harmbench",
    show_default=True,
    help="Judge evaluator type.",
)
@click.option(
    "--timeout",
    type=int,
    default=300,
    show_default=True,
    help="Per-attack timeout (seconds).",
)
@click.option(
    "--fail-fast/--no-fail-fast",
    default=False,
    show_default=True,
    help="Stop at first failed attack instead of continuing remaining attacks.",
)
@click.option(
    "--dry-run", is_flag=True, help="Validate scan plan without executing attacks."
)
@click.pass_context
@handle_errors
def scan(
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
    """⚡ Run a quick 3-attack security scan.

    Executes the primary jailbreak attacks from JAILBREAK_PROFILE in sequence.

    Example:
            hackagent eval --agent-name "my-agent" --agent-type "ollama" --endpoint "http://localhost:8000/chat"
    """
    run_quick_scan(
        ctx=ctx,
        agent_name=agent_name,
        agent_type=agent_type,
        endpoint=endpoint,
        dataset_preset=dataset_preset,
        limit=limit,
        judge_identifier=judge_identifier,
        judge_type=judge_type,
        timeout=timeout,
        fail_fast=fail_fast,
        dry_run=dry_run,
    )


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
