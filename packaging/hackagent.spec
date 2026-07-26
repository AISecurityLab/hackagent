# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""PyInstaller spec for the standalone ``hackagent`` binary.

Build with::

    uv run pyinstaller packaging/hackagent.spec

Produces a ``dist/hackagent/`` directory (onedir) containing a ``hackagent``
launcher. Onedir is used instead of onefile because onefile unpacks the whole
bundle to a temp directory on every launch, which is slow for an app this size.
"""

import os
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    copy_metadata,
)

PROJECT_ROOT = Path(SPECPATH).resolve().parent
BUILD_DIR = Path(workpath).resolve()

# ``importlib.metadata.version("hackagent")`` is used for ``--version`` and the
# ``version`` command. Ship the distribution metadata so it keeps working, and
# bake the version into a runtime hook as a belt-and-braces fallback.
datas = copy_metadata("hackagent")

# Textual and NiceGUI serve non-Python assets (CSS, static web files) from their
# package data, which the default import hooks do not collect.
for package in ("textual", "nicegui"):
    datas += collect_data_files(package)

# First-party non-Python assets (dataset taxonomies, bundled examples, docs).
datas += collect_data_files("hackagent", include_py_files=False)

hiddenimports = ["faiss"]

# Textual resolves widgets lazily through ``textual.widgets.__getattr__`` and the
# TUI views are imported by name, so static analysis never sees either of them.
hiddenimports += collect_submodules("textual")
hiddenimports += collect_submodules("hackagent.cli.tui")

_build_version = os.environ.get("HACKAGENT_BUILD_VERSION", "")
_runtime_hook = BUILD_DIR / "hackagent_runtime_version.py"
BUILD_DIR.mkdir(parents=True, exist_ok=True)
_runtime_hook.write_text(
    "import os\n"
    f"os.environ.setdefault('HACKAGENT_BUILD_VERSION', {_build_version!r})\n"
)

a = Analysis(
    [str(PROJECT_ROOT / "packaging" / "entrypoint.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[str(_runtime_hook)],
    excludes=["tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="hackagent",
    console=True,
    strip=False,
    upx=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="hackagent",
)
