# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""``hackagent run``: execute a campaign queued from the dashboard.

The dashboard queues a run for "a local machine"; this command claims it,
runs the stored campaign here with the user's own model keys, and reports
progress back to the server so the dashboard shows it live.
"""

from __future__ import annotations

import getpass
import json
import os
import signal
import socket
import sys
from contextlib import contextmanager
from typing import Any, Iterator, Optional
from uuid import UUID

import click
from rich.console import Console

from hackagent._version import get_version
from hackagent.interfaces.cli.commands.campaign import event_printer
from hackagent.interfaces.cli.utils import display_error, display_warning, handle_errors

console = Console()

EXIT_REFUSED = 1
EXIT_INVALID_KEY = 2


def _fail(message: str, code: int = EXIT_REFUSED) -> None:
    display_error(message)
    raise SystemExit(code)


def confirm_cancel() -> bool:
    """Ask whether to cancel the running campaign (patched in tests)."""
    try:
        return click.confirm("\nCancel this run?", default=False)
    except click.Abort:
        return True  # a second Ctrl-C at the prompt means yes


@contextmanager
def ask_before_cancelling(confirm=None) -> Iterator[None]:
    """Make Ctrl-C ask first; "yes" interrupts the run, "no" lets it go on.

    The interrupt is raised into the run, which records itself as cancelled.
    """

    def handler(signum: int, frame: Any) -> None:
        if (confirm or confirm_cancel)():
            raise KeyboardInterrupt
        console.print("[dim]Continuing the run.[/dim]")

    try:
        previous = signal.signal(signal.SIGINT, handler)
    except ValueError:  # not the main thread: keep the default behaviour
        yield
        return
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous)


def _check_key(store: Any) -> None:
    from hackagent.storage import InvalidApiKey

    try:
        store.check_key()
    except InvalidApiKey:
        _fail(
            "Your API key is not valid. Set one with: "
            "hackagent config set --api-key <key>",
            EXIT_INVALID_KEY,
        )


def _refuse_unless_runnable(detail: dict[str, Any]) -> None:
    status = detail.get("status")
    if detail.get("executor") != "local":
        _fail(
            f"This run executes on '{detail.get('executor')}', not on a local "
            "machine, so it cannot be run here."
        )
    if detail.get("claimed_by"):
        _fail(f"This run was already claimed by {detail['claimed_by']}.")
    if status != "PENDING":
        _fail(f"This run is {status}; only a queued (PENDING) run can be started.")


def _check_sdk_version(run_config: dict[str, Any]) -> None:
    from packaging.version import InvalidVersion, Version

    needed = run_config.get("sdk_version")
    if not needed:
        return
    try:
        have, want = Version(get_version()), Version(str(needed))
    except InvalidVersion:
        return
    if have < want:
        _fail(f"This run needs hackagent {needed} or newer: pip install -U hackagent")
    if have > want:
        display_warning(
            f"This run was queued with hackagent {needed}; you have {have}."
        )


def _check_environment(spec: Any) -> None:
    from hackagent.orchestrator.campaign.gateway import key_envs

    missing = sorted(key_envs(spec) - os.environ.keys())
    if missing:
        display_error("Set these variables with your model keys, then run again:")
        for name in missing:
            click.echo(f"export {name}=...")
        raise SystemExit(EXIT_REFUSED)


def _choose_run(store: Any, as_json: bool) -> Optional[str]:
    """List the queued local runs; return the one the user picks, if any."""
    runs = store.list_queued_local_runs()
    interactive = sys.stdin.isatty() and sys.stdout.isatty() and not as_json
    if as_json:
        click.echo(json.dumps(runs))
    elif not runs:
        console.print("No queued runs. Queue one from the dashboard first.")
    else:
        for number, run in enumerate(runs, 1):
            console.print(
                f"{number:>3}. {run['id']}  {run['agent_name']}  {run['timestamp']}",
                highlight=False,
            )
    if not runs or not interactive:
        return None
    number = click.prompt(
        "Run number", type=click.IntRange(1, len(runs)), default=1, show_default=True
    )
    return runs[number - 1]["id"]


@click.command(name="run")
@click.argument("run_id", required=False)
@click.option("--json", "as_json", is_flag=True, help="Emit events as JSON.")
@click.pass_context
@handle_errors
def run(ctx: click.Context, run_id: Optional[str], as_json: bool) -> None:
    """Run a campaign queued from the dashboard on this machine.

    Without RUN_ID, lists the queued runs of your organization.
    """
    from hackagent.orchestrator.execution import execute_run
    from hackagent.orchestrator.execution.execute import executable_spec
    from hackagent.storage import RunNotClaimable
    from hackagent.storage.remote import RemoteBackend

    config = ctx.obj["config"]
    config.require_remote()
    settings = config.settings

    store = RemoteBackend.connect(settings.base_url, settings.api_key)
    try:
        _check_key(store)
        if run_id is None:
            run_id = _choose_run(store, as_json)
            if run_id is None:
                return
        try:
            run_uuid = UUID(run_id)
        except ValueError:
            _fail(f"'{run_id}' is not a run id.")

        detail = store.get_run_detail(run_uuid)
        _refuse_unless_runnable(detail)
        run_config = detail.get("run_config") or {}
        _check_sdk_version(run_config)
        try:
            spec = executable_spec(run_config["campaign_config"], settings.base_url)
        except Exception as exc:
            _fail(f"This run's campaign cannot be loaded: {exc}")
        _check_environment(spec)

        if settings.dashboard_url and not as_json:
            console.print(
                f"Follow it at {settings.dashboard_url}/attacks?runId={run_uuid}"
            )
        try:
            with ask_before_cancelling():
                outcome = execute_run(
                    store,
                    run_uuid,
                    base_url=settings.base_url,
                    gateway_key=settings.api_key,
                    claimed_by=f"local:{socket.gethostname()} ({getpass.getuser()})",
                    on_event=event_printer(as_json),
                )
        except RunNotClaimable as exc:
            _fail(exc.note)
        except KeyboardInterrupt:
            _fail("Run cancelled.")
    finally:
        store.close()

    if as_json:
        click.echo(
            json.dumps(
                {
                    "run_id": str(run_uuid),
                    "status": outcome.status,
                    "note": outcome.note,
                }
            )
        )
    elif outcome.status == "COMPLETED":
        console.print(f"[green]Run {outcome.status.lower()}.[/green]")
    else:
        display_error(f"Run {outcome.status.lower()}: {outcome.note}")
    raise SystemExit(0 if outcome.status == "COMPLETED" else 1)


__all__ = ["run"]
