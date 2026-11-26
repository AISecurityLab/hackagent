# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


"""Show what past runs found."""

import json
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
@click.option("--json", "as_json", is_flag=True, help="Print the result as JSON.")
@click.pass_context
@handle_errors
def show(ctx, result_id, as_json):
    """Show one result: its goal, verdict, judges' notes and the reply.

    Find RESULT_ID with: hackagent results summary --goals --ids
    """

    cli_config: CLIConfig = ctx.obj["config"]
    cli_config.validate()

    try:
        from hackagent import HackAgent

        session = HackAgent(cli_config.settings)
        with console.status(f"Fetching result {result_id}…"):
            result = session.result(result_id)
            audit = None if as_json else _campaign_audit(session, result)

        if as_json:
            click.echo(json.dumps(_result_json(result), indent=2))
            return
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
    """The goal, the verdict and the evidence for it: what the target said."""
    from hackagent.interfaces import results as said

    table = Table(title="Result", show_header=False)
    table.add_column("Property", style="accent")
    table.add_column("Value", overflow="fold")
    table.add_row("ID", str(result.id))
    table.add_row("Run", str(getattr(result, "run_id", "") or "—"))
    table.add_row("Verdict", said.verdict_of(result))
    created = getattr(result, "created_at", None)
    if isinstance(created, datetime):
        table.add_row("Recorded", created.strftime("%Y-%m-%d %H:%M:%S"))
    console.print(table)

    display_heading("Goal")
    console.print(str(getattr(result, "goal", "") or "—"), markup=False)
    notes = str(getattr(result, "evaluation_notes", "") or "").strip()
    if notes:
        display_heading("Judges' notes")
        console.print(notes, style="secondary", markup=False)
    metadata = getattr(result, "metadata", None) or {}
    reply = str(metadata.get("response") or "").strip()
    display_heading("Reply")
    console.print(reply or "nothing recorded", style="secondary", markup=False)


def _result_json(result) -> dict:
    """The result as JSON: every recorded field, ids and dates as strings."""
    from hackagent.interfaces import results as said

    data = result.model_dump(mode="json") if hasattr(result, "model_dump") else {}
    data["verdict"] = said.verdict_of(result)
    return data


@results.command()
@click.option(
    "--limit",
    default=10,
    show_default=True,
    type=click.IntRange(min=1),
    help="How many of the latest campaigns to show.",
)
@click.option("--goals", is_flag=True, help="List each attack's goals and verdicts.")
@click.option(
    "--ids",
    is_flag=True,
    help="With --goals, print each result's id, for: hackagent results show.",
)
@click.pass_context
@handle_errors
def summary(ctx, limit, goals, ids):
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
                if ids:
                    console.print(f"    [secondary]{' ' * 12}{result.id}[/secondary]")
            if more := said.more_line(said.MAX_GOALS, len(items)):
                console.print(f"    {more}")
