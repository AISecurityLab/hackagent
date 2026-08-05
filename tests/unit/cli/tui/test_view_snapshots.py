# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Textual snapshot tests for the TUI views extracted into packages.

These lock the rendered output of ``AttacksTab`` and ``ResultsTab`` so that
future refactors of ``hackagent.cli.tui.views.*`` cannot silently change the
layout. Regenerate the snapshots with::

    uv run pytest tests/unit/cli/tui --snapshot-update

``snap_compare`` also accepts a file path, but ``pytest-textual-snapshot``
resolves it to an absolute path and hands it to Textual's ``import_app``,
which runs it through ``shlex.split``. When the repository checkout lives
under a directory containing a space (e.g. ``.../VS Code/hackagent``), that
split mangles the path and the import fails with ``No module named ...``.
Loading the app class ourselves and passing a fresh instance sidesteps
``import_app``/``shlex`` entirely.
"""

import importlib.util
from pathlib import Path

import pytest

_APPS = Path(__file__).parent / "snapshot_apps"

# Both tabs render tall panels (the Attacks strategy form, the Results detail
# pane); the large terminal makes the snapshots cover them rather than just the
# top few rows. The narrow size additionally locks the responsive layout.
_LARGE_TERMINAL = (140, 50)
_NARROW_TERMINAL = (80, 24)


def _load_app_instance(app_file: str, class_name: str):
    """Import ``app_file`` fresh and return a new instance of ``class_name``.

    A fresh module/instance per call avoids reusing an already-run Textual
    ``App`` object across parametrized cases that share the same file.
    """
    path = _APPS / app_file
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, class_name)()


@pytest.mark.parametrize(
    ("app_file", "class_name", "terminal_size"),
    [
        ("attacks_tab_app.py", "AttacksTabApp", _LARGE_TERMINAL),
        ("results_tab_app.py", "ResultsTabApp", _LARGE_TERMINAL),
        ("attacks_tab_app.py", "AttacksTabApp", _NARROW_TERMINAL),
    ],
    ids=["attacks-large", "results-large", "attacks-narrow"],
)
def test_view_renders(snap_compare, app_file, class_name, terminal_size):
    app_instance = _load_app_instance(app_file, class_name)
    assert snap_compare(app_instance, terminal_size=terminal_size)
