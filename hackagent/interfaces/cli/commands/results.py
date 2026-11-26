# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


"""
Results Commands

View and manage attack results.
"""

from datetime import datetime

import click
from rich.table import Table

from hackagent.interfaces.cli.config import CLIConfig
from hackagent.interfaces.cli.utils import (
    Failed,
    console,
    display_heading,
    display_info,
    display_warning,
    handle_errors,
)


@click.group()
def results():
    """Show what past runs found."""


@results.command()
@click.argument("result_id")
@click.pass_context
@handle_errors
def show(ctx, result_id):
    """Show detailed information about a specific result"""

    cli_config: CLIConfig = ctx.obj["config"]
    cli_config.validate()

    try:
        from hackagent import HackAgent

        session = HackAgent(cli_config.settings)
        with console.status(f"Fetching result {result_id}…"):
            result = session.result(result_id)
            audit = _campaign_audit(session, result)

        _display_result_details(result)
        if audit:
            _display_audit(audit)

    except click.ClickException:
        raise
    except Exception as e:
        raise Failed(f"Failed to fetch result: {e}")


def _campaign_audit(session, result):
    """The judge audit of the campaign this result's run belongs to, if any."""
    run_id = getattr(result, "run_id", None)
    if not run_id:
        return None
    try:
        run = session.run(run_id)
        campaign_run_id = getattr(run, "campaign_run_id", None)
        if not campaign_run_id:
            return None
        return getattr(session.campaign_run(campaign_run_id), "audit", None)
    except Exception:
        # The audit is context for the result, not a reason to fail showing it.
        return None


def _display_audit(audit) -> None:
    """Show how the campaign's judge panel scored in its audit."""
    from hackagent.interfaces.audit import audit_markup

    try:
        console.print()
        console.print(audit_markup(audit))
    except (TypeError, ValueError):
        display_warning("Judge audit recorded but could not be read.")


def _display_result_details(result) -> None:
    """Display detailed information about a result"""

    # Basic info table
    table = Table(title="Result", show_header=True, header_style="heading")
    table.add_column("Property", style="accent")
    table.add_column("Value")

    table.add_row("ID", str(result.id))

    if hasattr(result, "agent_name"):
        table.add_row("Agent", result.agent_name)

    if hasattr(result, "attack_type"):
        table.add_row("Attack Type", result.attack_type)

    if hasattr(result, "evaluation_status"):
        status = result.evaluation_status
        if hasattr(status, "value"):
            status = status.value
        table.add_row("Status", str(status))

    # Format dates
    if hasattr(result, "created_at") and result.created_at:
        try:
            if isinstance(result.created_at, datetime):
                created = result.created_at.strftime("%Y-%m-%d %H:%M:%S")
            else:
                created = str(result.created_at)
        except (AttributeError, ValueError, TypeError):
            created = str(result.created_at)
        table.add_row("Created", created)

    console.print(table)

    # Show additional data if available
    if hasattr(result, "data") and result.data:
        display_heading("Data")
        try:
            import json

            if isinstance(result.data, dict):
                data_str = json.dumps(result.data, indent=2)
            else:
                data_str = str(result.data)
            console.print(data_str, style="secondary", markup=False)
        except (json.JSONDecodeError, TypeError, AttributeError):
            console.print(str(result.data), style="secondary", markup=False)


@results.command()
@click.option(
    "--limit",
    default=10,
    show_default=True,
    type=click.IntRange(min=1),
    help="How many of the latest campaigns to show.",
)
@click.option("--goals", is_flag=True, help="List each attack's goals and verdicts.")
@click.pass_context
@handle_errors
def summary(ctx, limit, goals):
    """Show what the latest campaigns found.

    Each campaign, then each of its attacks, as the terminal app's Results
    shows them; with --goals, the goals each attack tried and how each went.
    """
    from hackagent import HackAgent
    from hackagent.interfaces import results as said

    cli_config: CLIConfig = ctx.obj["config"]
    cli_config.validate()
    session = HackAgent(cli_config.settings)
    with console.status("Reading results…"):
        outline = said.read_outline(session)
        campaigns = said.newest_first(outline["campaigns"])[:limit]
        shown = {str(campaign.id) for campaign in campaigns}
        runs = [
            run
            for run in outline["runs"]
            if str(getattr(run, "campaign_run_id", "") or "") in shown
        ]
        found = {str(run.id): said.read_results(session, run) for run in runs}
    counted = {run_id: said.count(items) for run_id, items in found.items()}

    total = len(outline["campaigns"])
    if not total:
        display_info("No campaign recorded here yet.")
        return
    display_heading(
        f"{len(campaigns)} of {total} campaigns"
        if total > len(campaigns)
        else f"{total} {'campaign' if total == 1 else 'campaigns'}"
    )
    for campaign in campaigns:
        console.print()
        console.print(
            said.campaign_line(
                campaign,
                said.runs_of(runs, campaign),
                counted,
                outline["agents"],
            )
        )
        audit = said.audit_lines(getattr(campaign, "audit", None))
        if audit is not None:
            console.print(f"  {audit[0]}")
        for run in said.runs_of(runs, campaign):
            console.print(f"  {said.attack_line(run, counted, outline['attacks'])}")
            if not goals:
                continue
            items = found[str(run.id)]
            for result in items[: said.MAX_GOALS]:
                console.print(f"    {said.goal_line(result)}")
            if more := said.more_line(said.MAX_GOALS, len(items)):
                console.print(f"    {more}")
