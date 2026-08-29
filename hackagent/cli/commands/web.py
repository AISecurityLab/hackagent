# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
``hackagent web`` — web dashboard command.

In local mode, starts a NiceGUI server backed by local SQLite and serves the
dashboard at http://<host>:<port>/.

In remote mode (API key configured), opens the cloud dashboard at
https://app.hackagent.dev.
"""

import os
import signal
import socket
import subprocess
import time

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
    "--no-browser",
    is_flag=True,
    default=False,
    help="Do not auto-open a browser tab on start.",
)
@click.pass_context
def web(ctx, host, port, db_path, no_browser):
    """🌐 Launch the web dashboard.

    Local mode: starts a local web server that serves the dashboard.
    Remote mode: opens the HackAgent cloud dashboard.

    \b
    Examples:
      hackagent web                    # http://127.0.0.1:7860 (default)
      hackagent web --port 8080        # custom port
      hackagent web --host 0.0.0.0     # expose on all interfaces
      hackagent web --no-browser       # skip opening a browser tab
    """
    from hackagent.cli.config import CLIConfig

    cli_config: CLIConfig = ctx.obj["config"]

    # In remote mode, open the cloud dashboard directly instead of serving local UI.
    if cli_config.api_key:
        cloud_url = "https://app.hackagent.dev"
        console.print(
            "[dim]Remote mode detected: using HackAgent cloud dashboard.[/dim]"
        )
        console.print(f"[cyan]{cloud_url}[/cyan]")
        if not no_browser:
            import webbrowser

            opened = webbrowser.open(cloud_url)
            if not opened:
                console.print(
                    "[yellow]⚠️ Could not auto-open browser. Open the URL above manually.[/yellow]"
                )
        return

    try:
        from flask import Flask  # noqa: F401
    except ImportError:
        console.print(
            "[bold red]❌ Flask is required for the web dashboard.[/bold red]"
        )
        console.print("\n[cyan]Install with:[/cyan]")
        console.print("  pip install 'hackagent[web]'")
        console.print("  # or")
        console.print("  pip install flask")
        ctx.exit(1)
        return

    from hackagent.server.dashboard import create_app

    # ── Select backend ────────────────────────────────────────────────────────
    from hackagent.server.storage.local import LocalBackend

    backend = LocalBackend(db_path=db_path)

    # ── Create app ────────────────────────────────────────────────────────────
    app = create_app(backend=backend)

    url = f"http://{host}:{port}"

    console.print()
    console.print("[bold]🌐  HackAgent Dashboard[/bold]")
    console.print(f"    [cyan]→  {url}[/cyan]")
    mode_label = "local"
    console.print(f"    Mode : [cyan]{mode_label}[/cyan]")
    if mode_label == "local":
        resolved_db = db_path or "~/.local/share/hackagent/hackagent.db"
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
        ctx.exit(1)
        return

    # ── Serve (NiceGUI handles browser auto-open via show=...) ──────────────
    app.run(host=host, port=port, show=not no_browser)
