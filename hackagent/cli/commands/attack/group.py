# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The ``hackagent eval`` command group."""

from typing import Optional

import click
from rich.console import Console

from hackagent.cli.utils import (
    handle_errors,
)


from hackagent.cli.commands.scan import run_quick_scan


console = Console()


@click.group(name="eval", invoke_without_command=True)
@click.option("--agent-name", help="Target agent name")
@click.option(
    "--agent-type",
    type=str,
    default="other",
    show_default=True,
    help="Agent type (e.g., google-adk, litellm, langchain, openai-sdk, mcp, a2a, or other)",
)
@click.option(
    "--endpoint",
    help="Agent endpoint URL. For OpenAI-compatible endpoints, use a base URL ending with /v1.",
)
@click.option(
    "--dataset",
    "dataset_preset",
    default=None,
    help="Dataset preset for evaluation campaign (default: first PRIMARY dataset in JAILBREAK_PROFILE).",
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
    "--dry-run",
    is_flag=True,
    help="Validate evaluation campaign plan without executing attacks.",
)
@click.pass_context
@handle_errors
def eval_cmd(
    ctx: click.Context,
    agent_name: Optional[str],
    agent_type: str,
    endpoint: Optional[str],
    dataset_preset: Optional[str],
    limit: int,
    judge_identifier: str,
    judge_type: str,
    timeout: int,
    fail_fast: bool,
    dry_run: bool,
) -> None:
    """🚀 Evaluate AI agent security.

    - `hackagent eval` runs the evaluation campaign.
    - `hackagent eval <strategy>` runs a specific attack strategy.
    """
    if ctx.invoked_subcommand is not None:
        return

    if not agent_name or not endpoint:
        raise click.ClickException(
            "Evaluation campaign requires --agent-name and --endpoint. "
            "For a specific attack use: hackagent eval <strategy> ..."
        )

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
