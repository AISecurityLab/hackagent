# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Textual snapshot tests for the TUI views extracted into packages.

These lock the rendered output of ``AttacksTab`` and ``ResultsTab`` so that
future refactors of ``hackagent.cli.tui.views.*`` cannot silently change the
layout. Regenerate the snapshots with::

    uv run pytest tests/unit/cli/tui --snapshot-update
"""

from pathlib import Path

import pytest

_APPS = Path(__file__).parent / "snapshot_apps"

# Both tabs render tall panels (the Attacks strategy form, the Results detail
# pane); the large terminal makes the snapshots cover them rather than just the
# top few rows. The narrow size additionally locks the responsive layout.
_LARGE_TERMINAL = (140, 50)
_NARROW_TERMINAL = (80, 24)


@pytest.mark.parametrize(
    ("app_file", "terminal_size"),
    [
        ("attacks_tab_app.py", _LARGE_TERMINAL),
        ("results_tab_app.py", _LARGE_TERMINAL),
        ("attacks_tab_app.py", _NARROW_TERMINAL),
    ],
)
def test_view_renders(snap_compare, app_file, terminal_size):
    assert snap_compare(_APPS / app_file, terminal_size=terminal_size)
