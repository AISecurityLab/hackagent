# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the standalone ``hackagent`` binary.

Builds a one-dir (not one-file) bundle: startup is far faster than
--onefile's per-launch unpack-to-tempdir, at the cost of shipping a
directory instead of a single file. Release automation archives the
directory (tar.gz/zip) so the download is still one file.
"""

import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

datas = []
# importlib.metadata.version("hackagent") is called at import time in
# hackagent/cli/main.py — a frozen binary has no installed distribution
# metadata by default without this.
datas += copy_metadata("hackagent")
# hackagent ships non-.py data (datasets/omnisafebench/*.json, examples/**,
# server/dashboard/templates/*, server/api/scripts/*) that PyInstaller's
# default import hook does not collect for first-party packages.
datas += collect_data_files("hackagent")
datas += collect_data_files("textual")
datas += collect_data_files("nicegui")

hiddenimports = []
# textual.widgets and nicegui both lazily import internal submodules via
# module-level __getattr__, which PyInstaller's static bytecode analysis
# does not follow (confirmed: frozen builds without this raise
# ModuleNotFoundError: No module named 'textual.widgets._tab_pane').
hiddenimports += collect_submodules("textual")
hiddenimports += collect_submodules("nicegui")

a = Analysis(
    [os.path.join(SPECPATH, "entrypoint.py")],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="hackagent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="hackagent",
)
