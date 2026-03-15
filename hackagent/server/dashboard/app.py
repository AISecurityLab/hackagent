# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""HackAgent Dashboard — NiceGUI application factory.

Public API:
    create_app(backend=None, db_path=None) -> _DashboardApp
    _DashboardApp.run(host, port, show)
"""

from __future__ import annotations

from typing import Optional

from nicegui import ui

from ._api import register_api
from ._helpers import _BRAND
from ._page import DashboardPage


# ── App wrapper ───────────────────────────────────────────────────────────────


class _DashboardApp:
    """Return value of ``create_app()`` — wraps ``ui.run()``."""

    def run(
        self,
        host: str = "127.0.0.1",
        port: int = 7860,
        show: bool = True,
        **_kwargs,  # absorb legacy Flask kwargs (debug=, use_reloader=)
    ) -> None:
        ui.run(
            host=host,
            port=port,
            title="HackAgent Dashboard",
            show=show,
            reload=False,
            storage_secret="hackagent-local-v1",
            favicon="🛡️",
        )


# ── App factory ───────────────────────────────────────────────────────────────


def create_app(
    backend=None,
    db_path: Optional[str] = None,
) -> _DashboardApp:
    """Register REST API routes and the NiceGUI UI page.

    Args:
        backend: Any ``StorageBackend``-compatible instance.
        db_path: SQLite path override (only used when *backend* is None).

    Returns:
        A ``_DashboardApp`` whose ``.run()`` starts the NiceGUI server.
    """
    if backend is None:
        from hackagent.server.storage.local import LocalBackend

        backend = LocalBackend(db_path=db_path)

    register_api(backend)

    @ui.page("/")
    async def index():
        ui.colors(primary=_BRAND)
        page = DashboardPage(backend)
        await page.build()

    return _DashboardApp()
