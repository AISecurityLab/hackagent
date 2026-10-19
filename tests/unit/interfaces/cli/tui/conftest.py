# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Keep the TUI tests off this machine's real database.

A view that reads past runs falls back to the local store, which resolves to
``~/.local/share/hackagent`` unless told otherwise. A test must neither read
whatever runs the developer happens to have nor write into their database, so
every test in this package gets one of its own.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setenv("HACKAGENT_DB_PATH", str(tmp_path / "hackagent.db"))
