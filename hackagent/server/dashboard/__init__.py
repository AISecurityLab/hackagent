# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
HackAgent Community Edition Dashboard

A lightweight, self-hosted web dashboard that reads directly from the local
SQLite storage (or a remote backend when an API key is configured).

Usage:
    from hackagent.server.dashboard import create_app

    app = create_app()          # uses ~/.local/share/hackagent/hackagent.db
    app.run(host="127.0.0.1", port=7860)

Or via the CLI:
    hackagent web
    hackagent web --port 8080 --no-browser
"""

from .app import create_app

__all__ = ("create_app",)
