# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
``hackagent web`` — web dashboard command.

Starts a NiceGUI server that reads from the local SQLite backend
(or the remote backend when an API key is configured) and serves the
dashboard at http://<host>:<port>/.
"""

import threading
import time
import webbrowser

import click
import httpx
from rich.console import Console

console = Console()


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

    Starts a local web server that serves a full-featured security testing
    dashboard.  Works in both offline mode (SQLite) and online mode (remote
    API with an API key).

    \b
    Examples:
      hackagent web                    # http://127.0.0.1:7860 (default)
      hackagent web --port 8080        # custom port
      hackagent web --host 0.0.0.0     # expose on all interfaces
      hackagent web --no-browser       # skip opening a browser tab
    """
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

    from hackagent.cli.config import CLIConfig
    from hackagent.server.dashboard import create_app

    cli_config: CLIConfig = ctx.obj["config"]

    # ── Select backend ────────────────────────────────────────────────────────
    backend = None
    if cli_config.api_key:
        try:
            from hackagent.server.client import AuthenticatedClient
            from hackagent.server.storage.remote import RemoteBackend

            client = AuthenticatedClient(
                base_url=cli_config.base_url,
                token=cli_config.api_key,
                # Never disable HTTP timeouts in web mode: a stuck remote call
                # would otherwise keep the dashboard loading forever.
                timeout=httpx.Timeout(15.0, connect=5.0, read=15.0, write=15.0),
            )
            candidate_backend = RemoteBackend(client=client)
            # Preflight check to fail fast on invalid/unreachable remote config.
            candidate_backend.get_context()
            backend = candidate_backend
            console.print("[dim]Using remote backend.[/dim]")
        except Exception as exc:
            console.print(
                f"[yellow]⚠️  Could not connect to remote backend ({exc}). "
                "Falling back to local SQLite.[/yellow]"
            )

    if backend is None:
        from hackagent.server.storage.local import LocalBackend

        backend = LocalBackend(db_path=db_path)

    # ── Create app ────────────────────────────────────────────────────────────
    app = create_app(backend=backend)

    url = f"http://{host}:{port}"

    console.print()
    console.print("[bold]🌐  HackAgent Dashboard[/bold]")
    console.print(f"    [cyan]→  {url}[/cyan]")
    mode_label = "remote" if backend.__class__.__name__ == "RemoteBackend" else "local"
    console.print(f"    Mode : [cyan]{mode_label}[/cyan]")
    if mode_label == "local":
        resolved_db = db_path or "~/.local/share/hackagent/hackagent.db"
        console.print(f"    DB   : [dim]{resolved_db}[/dim]")
    console.print()
    console.print("    Press [bold]Ctrl+C[/bold] to stop.\n")

    # ── Free port if still occupied by a previous instance ──────────────────
    import signal
    import socket

    def _free_port(host: str, port: int) -> None:
        """Kill any process listening on host:port so we can bind cleanly."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((host, port)) != 0:
                return  # port already free
        try:
            import subprocess

            out = subprocess.check_output(
                ["lsof", "-t", "-i", f"TCP:{port}", "-sTCP:LISTEN"],
                text=True,
            ).strip()
            for pid in out.splitlines():
                pid = pid.strip()
                if pid.isdigit():
                    console.print(
                        f"[yellow]Killing previous process on port {port} (PID {pid})…[/yellow]"
                    )
                    import os

                    os.kill(int(pid), signal.SIGTERM)
            import time

            time.sleep(0.5)
        except Exception:
            pass

    _free_port(host, port)

    # ── Serve (NiceGUI opens the browser automatically when show=True) ────────
    app.run(host=host, port=port, show=not no_browser)
    # ── Auto-open browser ─────────────────────────────────────────────────────
    if not no_browser:

        def _open_browser():
            time.sleep(1.0)
            webbrowser.open(url)

        threading.Thread(target=_open_browser, daemon=True).start()

    # ── Serve ─────────────────────────────────────────────────────────────────
    app.run(host=host, port=port, debug=False, use_reloader=False)
