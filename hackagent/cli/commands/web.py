# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
``hackagent web`` — web dashboard command.

In local mode, starts a NiceGUI server backed by local SQLite and serves the
dashboard at http://<host>:<port>/.

In remote mode (API key configured), opens the cloud dashboard at
https://app.hackagent.dev.
"""

import click
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
        console.print("[bold red]❌ Flask is required for the web dashboard.[/bold red]")
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

    # ── Serve (NiceGUI handles browser auto-open via show=...) ──────────────
    app.run(host=host, port=port, show=not no_browser)
