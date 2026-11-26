# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Run declarative campaign files (``campaign.yaml``) from the CLI.

``hackagent campaign run`` loads a campaign, applies any run-time endpoint
overrides, waits for local servers, and executes it; ``validate`` resolves it
(goals, models, judges) without attacking, so configuration errors surface
before a run starts; ``schema`` prints the campaign format as JSON Schema. Both build on
:mod:`hackagent.orchestrator.campaign.overrides`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import click
from rich.markup import escape
from rich.table import Table

from hackagent.interfaces.checks import issue_markup, ready_markup, to_fix_markup
from hackagent.interfaces.cli.utils import (
    Failed,
    console,
    display_error,
    display_success,
    handle_errors,
)


@click.group()
def campaign() -> None:
    """Check and run campaign files (campaign.yaml)."""


@campaign.command("list")
def list_attacks() -> None:
    """List available attack techniques, their category and tags."""
    from hackagent.client import catalog_entries

    table = Table(title="Campaign attacks", header_style="heading")
    table.add_column("Name", style="name", no_wrap=True)
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
            help="Repoint attack role models (also: --decorator-endpoint).",
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
        click.option(
            "--wait-for-ollama",
            type=float,
            default=0.0,
            show_default=True,
            metavar="SECONDS",
            help="Wait this long for Ollama to answer before giving up.",
        ),
        click.option(
            "--ollama-pid",
            type=int,
            help="Stop waiting if this Ollama process exits.",
        ),
        click.option(
            "--wait-for-server",
            type=float,
            default=0.0,
            show_default=True,
            metavar="SECONDS",
            help="Wait this long for OpenAI-compatible servers to answer.",
        ),
        click.option(
            "--server-pid",
            type=int,
            help="Stop waiting if the target's server process exits.",
        ),
        click.option(
            "--judge-server-pid",
            type=int,
            help="Stop waiting if the judges' server process exits.",
        ),
        click.option(
            "--attacker-server-pid",
            type=int,
            help="Stop waiting if the attack models' server process exits.",
        ),
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
        apply_endpoint_overrides,
        campaign_issues,
    )

    values = _load_or_report(Path(file)).model_dump(mode="json")
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
    spec, issues = campaign_issues(values)
    if spec is None:
        # The options given made the file invalid (an override, a count).
        _report(issues)
        raise SystemExit(1)
    return spec, values


@campaign.command()
@click.argument("file", default="campaign.yaml", type=click.Path(dir_okay=False))
@click.option("--dry-run", is_flag=True, help="Resolve and report without attacking.")
@click.option(
    "--json", "as_json", is_flag=True, help="Print the run's summary as JSON on stdout."
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
        route_library_logs,
        setup_package_logging,
        show_run,
        suppress_noisy_libraries,
    )
    from hackagent.core.credentials import run_environment
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
    #: What the run's ``${VARIABLE}`` references read besides the environment.
    run_env: dict[str, str] = {}
    if not tracked:
        if storage.backend == "remote":
            gateway_url = storage.base_url or settings.base_url
            # Nothing is sent in a dry run; any key lets the models build.
            gateway_key = storage.api_key or settings.api_key
        else:
            gateway_url, gateway_key = settings.base_url, settings.api_key
        spec = bind_gateway(spec, gateway_url)
        if uses_gateway(spec) and not gateway_key:
            raise Failed(
                "This campaign uses the HackAgent gateway, which needs an API "
                "key: export HACKAGENT_API_KEY=<key>"
            )
        if gateway_key:
            # The selected key, never one already in the environment: the
            # gateway models were just bound to the selected server.
            run_env[GATEWAY_KEY_ENV] = gateway_key

    setup_package_logging()
    suppress_noisy_libraries("httpx", "httpcore", "LiteLLM")
    route_library_logs()

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
            raise Failed(str(exc)) from exc

    with show_run(as_json), run_environment(run_env):
        if tracked:
            outcome = execute_spec(spec, settings=settings)
        else:
            outcome = None
            result = run_campaign(spec, settings=settings)
    if outcome is not None:
        if outcome.result is None:
            display_error(outcome.note or f"Campaign {outcome.status.lower()}.")
            raise SystemExit(1)
        result = outcome.result
        completed = outcome.status == "COMPLETED"
    else:
        completed = True
    report = summary(result)
    report["output_directory"] = spec.execution.output.directory
    if as_json:
        click.echo(json.dumps(report))
    # Otherwise the run's log has said it: the summary is its last lines.
    raise SystemExit(0 if report["succeeded"] and completed else 1)


@campaign.command()
@click.argument("file", default="campaign.yaml", type=click.Path(dir_okay=False))
@handle_errors
def validate(file: str) -> None:
    """Check a campaign as the TUI does, then resolve it (goals, models,
    judges) without attacking it."""
    from hackagent.interfaces.cli.logging_setup import shown_level
    from hackagent.orchestrator.campaign import ready_line, resolve_campaign

    spec = _load_or_report(Path(file))
    try:
        resolved = resolve_campaign(spec, settings=_runtime_settings())
    except Exception as exc:
        display_error(f"campaign rejected: {escape(str(exc))}")
        raise SystemExit(1) from exc
    # What resolving found, unless the log has just said it (at INFO).
    console.print(
        ready_markup("" if shown_level() <= logging.INFO else ready_line(resolved))
    )


def _load_or_report(path: Path) -> Any:
    """The campaign at ``path``, or each problem with it printed as the TUI
    shows it, and exit 1."""
    from hackagent.core.credentials import CredentialError
    from hackagent.orchestrator.campaign import CampaignInvalid, load_campaign

    try:
        return load_campaign(path)
    except CampaignInvalid as exc:
        _report(exc.issues)
    except (CredentialError, FileNotFoundError, ValueError) as exc:
        display_error(escape(str(exc)))
    raise SystemExit(1)


def _report(issues: Any) -> None:
    """Each problem, then how many there are to fix."""
    for issue in issues:
        console.print(issue_markup(issue))
    console.print(to_fix_markup(len(issues)))


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


__all__ = ["campaign"]
