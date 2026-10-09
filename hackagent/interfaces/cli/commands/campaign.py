# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Run declarative campaign files (``campaign.yaml``) from the CLI.

``hackagent campaign run`` loads a campaign, applies any run-time endpoint
overrides, waits for local servers, and executes it; ``validate`` resolves it
(goals, models, judges) without attacking, so configuration errors surface
before a run starts; ``schema`` prints the campaign format as JSON Schema. Both build on
:mod:`hackagent.orchestrator.campaign.overrides`, shared with
``scripts/run_campaign.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import click
from rich.console import Console
from rich.table import Table

from hackagent.interfaces.cli.utils import display_error, display_success, handle_errors

console = Console()


@click.group()
def campaign() -> None:
    """🎯 Run declarative campaign files (campaign.yaml)."""


def _endpoint_options(func):
    """Attach the run-time endpoint/server options shared by ``run``."""
    options = [
        click.option("--ollama-endpoint", help="Repoint every Ollama model."),
        click.option(
            "--openai-endpoint",
            help="Repoint the target and the judges sharing its endpoint.",
        ),
        click.option("--judge-endpoint", help="Repoint the other OpenAI judges."),
        click.option(
            "--attacker-endpoint",
            "--decorator-endpoint",
            "attacker_endpoint",
            help="Repoint attack role models.",
        ),
        click.option(
            "--output-directory",
            type=click.Path(file_okay=False),
            help="Override where result files are written.",
        ),
        click.option(
            "--concurrency",
            type=click.IntRange(min=1),
            help="Set attack/target/judge concurrency alike.",
        ),
        click.option("--wait-for-ollama", type=float, default=0.0, show_default=True),
        click.option("--ollama-pid", type=int),
        click.option("--wait-for-server", type=float, default=0.0, show_default=True),
        click.option("--server-pid", type=int),
        click.option("--judge-server-pid", type=int),
        click.option("--attacker-server-pid", type=int),
    ]
    for option in reversed(options):
        func = option(func)
    return func


def _prepare(
    file: str,
    overrides,
    *,
    dry_run: bool = False,
    concurrency: Optional[int] = None,
    output_directory: Optional[str] = None,
):
    """Load the campaign, apply overrides, and validate it to a spec.

    Returns ``(spec, values)`` — the validated :class:`CampaignSpec` and the
    plain dict ``wait_for_servers`` reads.
    """
    from hackagent.orchestrator.campaign import (
        CampaignSpec,
        apply_endpoint_overrides,
        load_campaign,
    )

    values = load_campaign(Path(file)).model_dump(mode="json")
    try:
        apply_endpoint_overrides(values, overrides)
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc
    execution = values["execution"]
    if dry_run:
        execution["dry_run"] = True
    if concurrency is not None:
        execution["concurrency"] = {
            "attack": concurrency,
            "target": concurrency,
            "judge": concurrency,
        }
    if output_directory:
        execution.setdefault("output", {})["directory"] = output_directory
    try:
        return CampaignSpec.model_validate(values), values
    except Exception as exc:
        raise click.ClickException(f"Invalid campaign: {exc}") from exc


@campaign.command()
@click.argument("file", default="campaign.yaml", type=click.Path(dir_okay=False))
@click.option("--dry-run", is_flag=True, help="Resolve and report without attacking.")
@click.option(
    "--json", "as_json", is_flag=True, help="Emit events and summary as JSON."
)
@_endpoint_options
@handle_errors
def run(
    file: str,
    dry_run: bool,
    as_json: bool,
    ollama_endpoint: Optional[str],
    openai_endpoint: Optional[str],
    judge_endpoint: Optional[str],
    attacker_endpoint: Optional[str],
    output_directory: Optional[str],
    concurrency: Optional[int],
    wait_for_ollama: float,
    ollama_pid: Optional[int],
    wait_for_server: float,
    server_pid: Optional[int],
    judge_server_pid: Optional[int],
    attacker_server_pid: Optional[int],
) -> None:
    """Run a campaign file against its (or overridden) model servers."""
    from hackagent.interfaces.cli.logging_setup import (
        setup_package_logging,
        suppress_noisy_libraries,
    )
    from hackagent.orchestrator.campaign import (
        EndpointOverrides,
        ServerReadiness,
        run_campaign,
        summary,
        wait_for_servers,
    )

    overrides = EndpointOverrides(
        ollama=ollama_endpoint,
        openai=openai_endpoint,
        judge=judge_endpoint,
        attacker=attacker_endpoint,
    )
    spec, values = _prepare(
        file,
        overrides,
        dry_run=dry_run,
        concurrency=concurrency,
        output_directory=output_directory,
    )

    setup_package_logging(default_level_str="INFO")
    suppress_noisy_libraries("httpx", "httpcore", "LiteLLM")

    if not spec.execution.dry_run:
        try:
            wait_for_servers(
                values,
                ServerReadiness(
                    wait_for_ollama=wait_for_ollama,
                    ollama_pid=ollama_pid,
                    wait_for_server=wait_for_server,
                    server_pid=server_pid,
                    judge_server_pid=judge_server_pid,
                    attacker_server_pid=attacker_server_pid,
                ),
            )
        except (ValueError, RuntimeError) as exc:
            raise click.ClickException(str(exc)) from exc

    def on_event(event: str, **payload: Any) -> None:
        if as_json:
            click.echo(json.dumps({"event": event, **payload}))
        elif event == "attack_started":
            console.print(f"[cyan]▶ {payload.get('attack')}[/cyan] started")
        elif event == "attack_finished":
            error = payload.get("error")
            mark = "[red]✗[/red]" if error else "[green]✓[/green]"
            console.print(f"{mark} {payload.get('attack')} finished")

    result = run_campaign(spec, on_event=on_event)
    report = summary(result)
    report["output_directory"] = spec.execution.output.directory
    if as_json:
        click.echo(json.dumps(report))
    else:
        _render_summary(report)
    raise SystemExit(0 if report["succeeded"] else 1)


@campaign.command()
@click.argument("file", default="campaign.yaml", type=click.Path(dir_okay=False))
@handle_errors
def validate(file: str) -> None:
    """Resolve a campaign (goals, models, judges) without attacking it."""
    from hackagent.orchestrator.campaign import load_campaign, resolve_campaign

    try:
        spec = load_campaign(Path(file))
        resolved = resolve_campaign(spec)
    except Exception as exc:
        display_error(f"Invalid campaign: {exc}")
        raise SystemExit(1) from exc

    table = Table(title=f"Campaign: {spec.campaign.name}", show_header=False)
    table.add_row("Goals", str(len(resolved.goals)))
    table.add_row("Attacks", ", ".join(a.name for a in resolved.attacks) or "—")
    table.add_row("Judges", str(len(spec.evaluation.judges)))
    table.add_row("Guardrails", "on" if spec.guardrails.active else "off")
    table.add_row("Classifier", "on" if resolved.classifier is not None else "off")
    table.add_row("Escalate", "on" if spec.execution.escalate else "off")
    console.print(table)
    display_success("Campaign is valid.")


@campaign.command()
@click.option(
    "-o",
    "--output",
    type=click.Path(dir_okay=False, writable=True),
    help="Write the schema to this file instead of printing it.",
)
def schema(output: Optional[str]) -> None:
    """Print the JSON Schema of campaign files, for editor autocompletion.

    \b
    Save it and point your editor at it, e.g. with the YAML language server:
      hackagent campaign schema -o campaign.schema.json
      # yaml-language-server: $schema=./campaign.schema.json
    """
    from hackagent.orchestrator.campaign.spec import campaign_json_schema

    text = json.dumps(campaign_json_schema(), indent=2) + "\n"
    if output:
        Path(output).write_text(text, encoding="utf-8")
        display_success(f"Schema written to {output}")
    else:
        click.echo(text, nl=False)


def _render_summary(report: dict[str, Any]) -> None:
    status = "[green]succeeded[/green]" if report["succeeded"] else "[red]failed[/red]"
    console.print(f"\nCampaign [bold]{report['campaign']}[/bold] {status}")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Attack")
    table.add_column("Attempts", justify="right")
    table.add_column("Successes", justify="right")
    table.add_column("Error")
    for attack in report["attacks"]:
        table.add_row(
            attack["name"],
            str(attack["attempts"]),
            str(attack["successes"]),
            attack["error"] or "",
        )
    console.print(table)
    if report.get("output_directory"):
        console.print(f"[dim]Output → {report['output_directory']}[/dim]")


__all__ = ["campaign"]
