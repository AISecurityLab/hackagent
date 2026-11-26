# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The web dashboard, served from this process: by ``hackagent web`` in the
foreground, and by the TUI's Dashboard screen in the background while the
app is open.

:func:`open_dashboard` builds the session and the app the same way for
both, and :func:`about` says the same about them; :class:`Served` keeps one
running on a thread of its own.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Optional

#: Where the dashboard listens unless told otherwise.
HOST, PORT = "127.0.0.1", 7860

#: The local database, as said when none is given.
DEFAULT_DB = "~/.local/share/hackagent/hackagent.db"


#: What ``hackagent web`` takes, and the TUI's Dashboard screen asks for:
#: each option's name, what it is called on screen, and what it is for.
OPTIONS: tuple[tuple[str, str, str], ...] = (
    ("host", "Host", "Host to bind the dashboard server."),
    ("port", "Port", "Port to run the dashboard server on."),
    ("db_path", "Database", f"SQLite database path (default: {DEFAULT_DB})."),
    (
        "local",
        "Local",
        "Read from the local database even when the remote backend is configured.",
    ),
)


def option_help(name: str) -> str:
    """What an option is for, as ``hackagent web --help`` says it."""
    return next(help for key, _, help in OPTIONS if key == name)


@dataclass
class Dashboard:
    """A dashboard ready to serve: its session, its app, where it is."""

    session: Any
    app: Any
    url: str
    db_path: Optional[str] = None


def open_dashboard(
    settings: Any,
    *,
    host: str = HOST,
    port: int = PORT,
    db_path: Optional[str] = None,
    force_local: bool = False,
) -> Dashboard:
    """The session and the dashboard's app over ``settings``.

    Raises ImportError when the web extra is not installed, and
    :class:`~hackagent.interfaces.web.MissingBundleError` when its build is
    missing; the session is closed then.
    """
    from hackagent import HackAgent
    from hackagent.core.settings import Mode
    from hackagent.interfaces.web import create_app

    if force_local:
        settings = replace(settings, backend=Mode.LOCAL)
    if db_path:
        db_path = db_path if db_path == ":memory:" else str(Path(db_path).expanduser())
        settings = replace(settings, db_path=db_path)
    session = HackAgent(settings)
    try:
        app = create_app(session, hosts=[host])
    except Exception:
        session.close()
        raise
    return Dashboard(session, app, f"http://{host}:{port}", db_path)


def about(dashboard: Dashboard) -> list[tuple[str, str]]:
    """What is worth knowing about it: where its data comes from."""
    from hackagent.core.settings import Mode

    if dashboard.session.settings.mode is Mode.REMOTE:
        return [
            ("backend", "remote"),
            ("API", str(dashboard.app.config["HACKAGENT_TARGET"])),
        ]
    return [("backend", "local"), ("database", dashboard.db_path or DEFAULT_DB)]


def in_use(host: str = HOST, port: int = PORT) -> bool:
    """Whether something already listens on ``host:port``."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        return probe.connect_ex((host, port)) == 0


class Served:
    """A dashboard served on a thread of its own, until :meth:`stop`."""

    def __init__(self, dashboard: Dashboard, host: str = HOST, port: int = PORT):
        from werkzeug.serving import make_server

        self.dashboard = dashboard
        # Each request is logged at INFO by werkzeug, on stderr: not on a
        # screen another app is drawing.
        logging.getLogger("werkzeug").setLevel(logging.WARNING)
        self._server = make_server(host, port, dashboard.app, threaded=True)
        self._thread = threading.Thread(
            target=self._server.serve_forever, name="dashboard", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self.dashboard.session.close()


__all__ = [
    "DEFAULT_DB",
    "Dashboard",
    "HOST",
    "PORT",
    "Served",
    "OPTIONS",
    "about",
    "option_help",
    "in_use",
    "open_dashboard",
]
