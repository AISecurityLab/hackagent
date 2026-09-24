# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
``hackagent web`` — serve the HackAgent dashboard locally.

Serves the bundled single-page app (the same one hosted at app.hackagent.dev)
from this process. With an API key configured its API calls are proxied to the
hosted API, with the key attached server-side; without one they are answered
read-only from the local SQLite store.
"""

import os
import signal
import socket
import subprocess
import threading
import time
import webbrowser

import click
from rich.console import Console

console = Console()


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
        console.print(
            f"[yellow]Stopping previous HackAgent instance on port {port} "
            f"(PID {pid})…[/yellow]"
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
                    console.print(
                        "[yellow]⚠️ Could not auto-open a browser. "
                        "Open the URL above manually.[/yellow]"
                    )
                return
            time.sleep(0.25)

    threading.Thread(target=_wait_and_open, daemon=True).start()


@click.command("web")
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    help="Host to bind the dashboard server.",
)
@click.option(
    "--port",
    default=7860,
    show_default=True,
    type=int,
    help="Port to run the dashboard server on.",
)
@click.option(
    "--db-path",
    default=None,
    help="SQLite database path (default: ~/.local/share/hackagent/hackagent.db).",
)
@click.option(
    "--local",
    "force_local",
    is_flag=True,
    default=False,
    help="Read from the local database even when an API key is configured.",
)
@click.option(
    "--no-browser",
    is_flag=True,
    default=False,
    help="Do not auto-open a browser tab on start.",
)
@click.pass_context
def web(ctx, host, port, db_path, force_local, no_browser):
    """🌐 Launch the web dashboard.

    With an API key configured, the dashboard shows your hosted HackAgent data;
    the key stays in this process and is never exposed to the browser. Without
    one, it shows the runs recorded in your local database (read-only).

    \b
    Examples:
      hackagent web                    # http://127.0.0.1:7860 (default)
      hackagent web --port 8080        # custom port
      hackagent web --local            # ignore the API key, read local runs
      hackagent web --no-browser       # skip opening a browser tab
    """
    from hackagent import HackAgent, Settings
    from hackagent.interfaces.cli.config import CLIConfig
    from hackagent.interfaces.web import MissingBundleError, create_app

    cli_config: CLIConfig = ctx.obj["config"]
    api_key = "" if force_local or not cli_config.api_key else cli_config.api_key
    resolve_kwargs = {"api_key": api_key, "base_url": cli_config.base_url}
    if db_path:
        resolve_kwargs["db_path"] = db_path
    session = HackAgent(Settings.resolve(**resolve_kwargs))

    try:
        app = create_app(session)
    except MissingBundleError as exc:
        session.close()
        console.print(f"[bold red]❌ {exc}[/bold red]")
        ctx.exit(1)
        return

    url = f"http://{host}:{port}"

    console.print()
    console.print("[bold]🌐  HackAgent Dashboard[/bold]")
    console.print(f"    [cyan]→  {url}[/cyan]")
    if session.settings.api_key:
        console.print("    Mode : [cyan]remote[/cyan]")
        console.print(f"    API  : [dim]{app.config['HACKAGENT_TARGET']}[/dim]")
    else:
        resolved_db = db_path or "~/.local/share/hackagent/hackagent.db"
        console.print("    Mode : [cyan]local[/cyan]")
        console.print(f"    DB   : [dim]{resolved_db}[/dim]")
    console.print()
    console.print("    Press [bold]Ctrl+C[/bold] to stop.\n")

    # ── Reclaim the port only if a previous HackAgent instance holds it ──────
    if not _free_port(host, port):
        console.print(
            f"[bold red]❌ Port {port} is already in use by another process.[/bold red]"
        )
        console.print(
            "[cyan]Pick a free port with[/cyan] [bold]--port <PORT>[/bold] "
            "[cyan]or stop the conflicting process first.[/cyan]"
        )
        session.close()
        ctx.exit(1)
        return

    if not no_browser:
        _open_browser_when_up(url, host, port)

    try:
        app.run(host=host, port=port, threaded=True)
    finally:
        session.close()
