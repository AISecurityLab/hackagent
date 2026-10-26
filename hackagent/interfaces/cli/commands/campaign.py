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
import os
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


@campaign.command("list")
def list_attacks() -> None:
    """List available attack techniques, their category and tags."""
    from hackagent.client import catalog_entries

    table = Table(title="Campaign attacks")
    table.add_column("Name", no_wrap=True)
    table.add_column("Category")
    table.add_column("Tags")
    table.add_column("Description")
    for entry in catalog_entries():
        table.add_row(
            entry["attack_type"],
            entry["category"],
            ", ".join(entry["tags"]),
            entry["description"],
        )
    console.print(table)


def _runtime_settings():
    """Return settings resolved by the root CLI, when invoked through it.

    The campaign command is also tested and usable as a standalone Click group,
    where no root ``CLIConfig`` exists; the runner then resolves settings itself.
    """
    ctx = click.get_current_context(silent=True)
    if ctx is None:
        return None
    root = ctx.find_root()
    config = (root.obj or {}).get("config") if isinstance(root.obj, dict) else None
    return getattr(config, "settings", None)


def event_printer(as_json: bool):
    """The run-progress callback shared by ``campaign run`` and ``run``."""

    def on_event(event: str, **payload: Any) -> None:
        if as_json:
            click.echo(json.dumps({"event": event, **payload}))
        elif event == "attack_started":
            console.print(f"[cyan]▶ {payload.get('attack')}[/cyan] started")
        elif event == "attack_finished":
            error = payload.get("error")
            mark = "[red]✗[/red]" if error else "[green]✓[/green]"
            console.print(f"{mark} {payload.get('attack')} finished")

    return on_event


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
    from hackagent.core.settings import Settings
    from hackagent.orchestrator.campaign import (
        GATEWAY_KEY_ENV,
        EndpointOverrides,
        ServerReadiness,
        bind_gateway,
        run_campaign,
        summary,
        wait_for_servers,
    )
    from hackagent.orchestrator.campaign.gateway import uses_gateway
    from hackagent.orchestrator.execution import execute_spec

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

    settings = _runtime_settings() or Settings.resolve()
    storage = spec.execution.storage
    # Remote storage names its server and key: the run is tracked there, and
    # execute_spec binds the gateway to it for execution only, so the
    # campaign is recorded with its gateway markers. A dry run never
    # touches remote storage.
    tracked = storage.backend == "remote" and not spec.execution.dry_run
    if not tracked:
        if storage.backend == "remote":
            gateway_url = storage.base_url or settings.base_url
            # Nothing is sent in a dry run; any key lets the models build.
            gateway_key = os.environ.get(storage.api_key_env or "") or settings.api_key
        else:
            gateway_url, gateway_key = settings.base_url, settings.api_key
        spec = bind_gateway(spec, gateway_url)
        if uses_gateway(spec) and not gateway_key:
            raise click.ClickException(
                "This campaign uses the HackAgent gateway; set an API key with: "
                "hackagent config set --api-key"
            )
        if gateway_key:
            os.environ.setdefault(GATEWAY_KEY_ENV, gateway_key)

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

    on_event = event_printer(as_json)

    if tracked:
        outcome = execute_spec(spec, on_event=on_event)
        if outcome.result is None:
            display_error(outcome.note or f"Campaign {outcome.status.lower()}.")
            raise SystemExit(1)
        result = outcome.result
        completed = outcome.status == "COMPLETED"
    else:
        result = run_campaign(spec, on_event=on_event, settings=settings)
        completed = True
    report = summary(result)
    report["output_directory"] = spec.execution.output.directory
    if as_json:
        click.echo(json.dumps(report))
    else:
        _render_summary(report)
    raise SystemExit(0 if report["succeeded"] and completed else 1)


@campaign.command()
@click.argument("file", default="campaign.yaml", type=click.Path(dir_okay=False))
@handle_errors
def validate(file: str) -> None:
    """Resolve a campaign (goals, models, judges) without attacking it."""
    from hackagent.orchestrator.campaign import (
        load_campaign,
        resolution_summary,
        resolve_campaign,
    )

    try:
        spec = load_campaign(Path(file))
        resolved = resolve_campaign(spec, settings=_runtime_settings())
    except Exception as exc:
        display_error(f"Invalid campaign: {exc}")
        raise SystemExit(1) from exc

    table = Table(title=f"Campaign: {spec.campaign.name}", show_header=False)
    for label, value in resolution_summary(resolved).items():
        table.add_row(label, value)
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
