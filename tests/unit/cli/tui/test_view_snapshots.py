# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Textual snapshot tests for the TUI views extracted into packages.

These lock the rendered output of ``AttacksTab`` and ``ResultsTab`` so that
future refactors of ``hackagent.cli.tui.views.*`` cannot silently change the
layout. Regenerate the snapshots with::

    uv run pytest tests/unit/cli/tui --snapshot-update
"""

import shlex
from pathlib import Path

import pytest

_APPS = Path(__file__).parent / "snapshot_apps"

# Both tabs render tall panels (the Attacks strategy form, the Results detail
# pane); the large terminal makes the snapshots cover them rather than just the
# top few rows. The narrow size additionally locks the responsive layout.
_LARGE_TERMINAL = (140, 50)
_NARROW_TERMINAL = (80, 24)


@pytest.fixture(autouse=True)
def _quote_app_path_for_import(monkeypatch):
    """Work around a ``textual`` bug when the repo path contains spaces.

    ``pytest_textual_snapshot.snap_compare`` resolves the app to an absolute
    path and hands the raw string to ``textual._import_app.import_app``,
    which immediately runs it through ``shlex.split``. Any space in the path
    (e.g. a checkout under a directory like ``.../VS Code/...``) is then
    parsed as an argument separator, so the importer looks for a module
    named after just the first path fragment. Quoting the path before it
    reaches ``shlex.split`` keeps it intact as a single token.
    """
    from textual import _import_app as textual_import_app

    original_import_app = textual_import_app.import_app

    def _patched_import_app(import_name: str):
        if import_name.endswith(".py") and " " in import_name:
            import_name = shlex.quote(import_name)
        return original_import_app(import_name)

    monkeypatch.setattr(textual_import_app, "import_app", _patched_import_app)


@pytest.mark.parametrize(
    ("app_file", "terminal_size"),
    [
        ("attacks_tab_app.py", _LARGE_TERMINAL),
        ("results_tab_app.py", _LARGE_TERMINAL),
        ("attacks_tab_app.py", _NARROW_TERMINAL),
    ],
    ids=["attacks-large", "results-large", "attacks-narrow"],
)
def test_view_renders(snap_compare, app_file, terminal_size):
    assert snap_compare(_APPS / app_file, terminal_size=terminal_size)
