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

# The Attacks tab renders its full strategy form; give it a tall terminal so
# the snapshot covers the whole configuration panel, not just the top rows.
_LARGE_TERMINAL = (140, 50)


@pytest.mark.parametrize(
    "app_file",
    ["attacks_tab_app.py", "results_tab_app.py"],
)
def test_view_renders(snap_compare, app_file):
    assert snap_compare(_APPS / app_file, terminal_size=_LARGE_TERMINAL)


def test_attacks_tab_narrow_terminal(snap_compare):
    """Locks the Attacks tab layout on a small terminal."""
    assert snap_compare(_APPS / "attacks_tab_app.py", terminal_size=(80, 24))
