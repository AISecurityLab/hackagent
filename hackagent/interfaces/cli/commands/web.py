# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
``hackagent web`` — serve the HackAgent dashboard locally.

Serves the bundled single-page app (the same one hosted at app.hackagent.dev)
from this process. With the ``remote`` storage backend its API calls are proxied
to the hosted API, with the key attached server-side; with ``local`` (the
default) they are answered from the local SQLite store, and campaigns launched
from the dashboard run on this machine, in this process.
"""

import os
import signal
import socket
import subprocess
import threading
import time
import webbrowser

import click
from rich.markup import escape

from hackagent.interfaces.dashboard import HOST, PORT, option_help

from hackagent.interfaces.cli.utils import (
    console,
    display_error,
    display_hint,
    display_warning,
)


def _port_in_use(host: str, port: int) -> bool:
    """Return True if a process is listening on ``host:port``."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def _listener_pids(port: int) -> list[str]:
    """Return the PIDs listening on ``port`` (POSIX only; empty otherwise)."""
    try:
        out = subprocess.check_output(
            ["lsof", "-t", "-i", f"TCP:{port}", "-sTCP:LISTEN"],
            text=True,
        ).strip()
    except Exception:
        return []
    return [line.strip() for line in out.splitlines() if line.strip().isdigit()]


def _is_hackagent_process(pid: str) -> bool:
    """Return True if ``pid``'s command line identifies a HackAgent process."""
    try:
        out = subprocess.check_output(
            ["ps", "-p", pid, "-o", "command="],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return False
    return "hackagent" in out.lower()


def _free_port(host: str, port: int) -> bool:
    """Reclaim ``host:port`` if a previous HackAgent dashboard holds it.

    Only a process whose command line identifies it as HackAgent is
    terminated. If the port is held by an unrelated process it is left
    untouched and ``False`` is returned so the caller can fail with a clear
    message instead of killing an unrelated service.
    """
    if not _port_in_use(host, port):
        return True  # port already free

    pids = _listener_pids(port)
    if not pids:
        # Could not enumerate the listener(s): refuse rather than risk a kill.
        return False

    for pid in pids:
        if not _is_hackagent_process(pid):
            return False  # foreign process — never kill it
        display_warning(
            f"Stopping the previous HackAgent dashboard on port {port} (PID {pid})…"
        )
        try:
            os.kill(int(pid), signal.SIGTERM)
        except Exception:
            return False

    # Give the terminated process a moment to release the socket before bind.
    time.sleep(0.5)
    return True


def _open_browser_when_up(url: str, host: str, port: int, timeout: float = 15.0):
    """Open ``url`` once the server accepts connections, in the background."""

    def _wait_and_open():
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if _port_in_use(host, port):
                if not webbrowser.open(url):
                    display_warning(
                        "Could not open a browser: open the address above yourself."
                    )
                return
            time.sleep(0.25)

    threading.Thread(target=_wait_and_open, daemon=True).start()


@click.command("web")
@click.option(
    "--host",
    default=HOST,
    show_default=True,
    help=option_help("host"),
)
@click.option(
    "--port",
    default=PORT,
    show_default=True,
    type=int,
    help=option_help("port"),
)
@click.option(
    "--db-path",
    default=None,
    help=option_help("db_path"),
)
@click.option(
    "--local",
    "force_local",
    is_flag=True,
    default=False,
    help=option_help("local"),
)
@click.option(
    "--no-browser",
    is_flag=True,
    default=False,
    help="Do not auto-open a browser tab on start.",
)
@click.pass_context
def web(ctx, host, port, db_path, force_local, no_browser):
    """Open the web dashboard.

    The terminal app's Dashboard screen serves it with the same options.

    With hackagent --backend remote web, the dashboard shows your hosted
    HackAgent data; the key stays in this process and is never exposed to
    the browser. With
    the default local backend, it shows the runs recorded in your local
    database, and campaigns you launch from it run on this machine.

    \b
    Examples:
      hackagent web                    # http://127.0.0.1:7860 (default)
      hackagent web --port 8080        # custom port
      hackagent web --local            # force the local backend
      hackagent web --no-browser       # skip opening a browser tab
    """
    from hackagent.interfaces.cli.config import CLIConfig
    from hackagent.interfaces.dashboard import about, open_dashboard

    cli_config: CLIConfig = ctx.obj["config"]
    try:
        from hackagent.interfaces.web import MissingBundleError

        dashboard = open_dashboard(
            cli_config.settings,
            host=host,
            port=port,
            db_path=db_path,
            force_local=force_local,
        )
    except ImportError as exc:
        display_error(f"The dashboard needs its dependencies: {exc}")
        display_hint("Install them", "pip install 'hackagent[web]'")
        ctx.exit(1)
        return
    except MissingBundleError as exc:
        display_error(escape(str(exc)))
        ctx.exit(1)
        return
    session, app, url = dashboard.session, dashboard.app, dashboard.url

    console.print()
    console.print("[heading]HackAgent dashboard[/heading]")
    console.print(f"  [accent]{url}[/accent]")
    for label, value in about(dashboard):
        console.print(f"  [secondary]{label:<8}[/secondary] {escape(value)}")
    console.print()
    console.print("  [secondary]ctrl+c to stop[/secondary]\n")

    # ── Reclaim the port only if a previous HackAgent instance holds it ──────
    if not _free_port(host, port):
        display_error(f"Port {port} is already in use by another process.")
        display_hint("Pick a free one", "hackagent web --port PORT")
        session.close()
        ctx.exit(1)
        return

    if not no_browser:
        _open_browser_when_up(url, host, port)

    try:
        app.run(host=host, port=port, threaded=True)
    finally:
        session.close()
