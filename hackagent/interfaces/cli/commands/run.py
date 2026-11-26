# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""``hackagent run``: execute a campaign queued from the dashboard.

The dashboard queues a run for "a local machine"; this command claims it,
runs the stored campaign here with the user's own model keys, and reports
progress back to the server so the dashboard shows it live.
"""

from __future__ import annotations

import json
import signal
import sys
from contextlib import contextmanager
from typing import Any, Iterator, Optional

import click

from hackagent.interfaces.cli.logging_setup import show_run
from hackagent.interfaces.cli.utils import (
    console,
    display_error,
    display_hint,
    display_info,
    display_success,
    display_warning,
    handle_errors,
)
from hackagent.interfaces.queued import REFUSED as EXIT_REFUSED


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
        display_info("Continuing the run.")

    try:
        previous = signal.signal(signal.SIGINT, handler)
    except ValueError:  # not the main thread: keep the default behaviour
        yield
        return
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous)


def _refuse(refused: Any) -> None:
    """Say why the run is refused, and exit with its code."""
    display_error(str(refused))
    for name in refused.missing:
        click.echo(f"export {name}=...")
    raise SystemExit(refused.code)


def _choose_run(store: Any, as_json: bool) -> Optional[str]:
    """List the queued local runs; return the one the user picks, if any."""
    from hackagent.interfaces.queued import queued_runs

    runs = queued_runs(store)
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
@click.option(
    "--json", "as_json", is_flag=True, help="Print the run's outcome as JSON on stdout."
)
@click.pass_context
@handle_errors
def run(ctx: click.Context, run_id: Optional[str], as_json: bool) -> None:
    """Run a campaign queued from the dashboard on this machine.

    Without RUN_ID, lists the queued runs of your organization.
    """
    from hackagent.interfaces import queued
    from hackagent.storage import RunNotClaimable

    config = ctx.obj["config"]
    config.require_remote()
    settings = config.settings

    try:
        store = queued.connect(settings)
    except queued.Refused as refused:
        _refuse(refused)
    try:
        if run_id is None:
            run_id = _choose_run(store, as_json)
            if run_id is None:
                return
        try:
            ready = queued.prepare(store, run_id, settings)
        except queued.Refused as refused:
            _refuse(refused)
        for warning in ready.warnings:
            display_warning(warning)
        run_uuid = ready.run_id

        follow = queued.follow_url(settings, run_uuid)
        if follow and not as_json:
            display_hint("Follow it", follow)
        try:
            with ask_before_cancelling(), show_run(as_json):
                outcome = queued.execute(store, ready, settings)
        except RunNotClaimable as exc:
            _fail(exc.note)
        except KeyboardInterrupt:
            _fail("Run cancelled.")
    finally:
        store.close(close_client=True)

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
        display_success(f"Run {outcome.status.lower()}.")
    else:
        display_error(f"Run {outcome.status.lower()}: {outcome.note}")
    raise SystemExit(0 if outcome.status == "COMPLETED" else 1)


__all__ = ["run"]
