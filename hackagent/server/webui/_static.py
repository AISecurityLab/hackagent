# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Locate the bundled HackAgent web UI (a static Next.js export).

The bundle is produced from the ``hackagent-webapp`` repository
(``npm run build:static``) and dropped into ``hackagent/server/webui/static``.
It is not tracked in git: a source checkout without a bundle simply has no web
UI, and ``hackagent web`` says so rather than failing obscurely.

PyInstaller collects the directory through ``collect_data_files("hackagent")``,
which preserves the package tree, so resolving relative to ``__file__`` works
both from source and from a frozen one-dir build.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

#: Marker file that distinguishes a real bundle from an empty placeholder dir.
_INDEX = "index.html"


def static_dir() -> Path:
    """Return the path the web UI bundle is expected at (may not exist)."""
    return Path(__file__).resolve().parent / "static"


def find_bundle() -> Optional[Path]:
    """Return the bundled web UI directory, or ``None`` if this build has none."""
    candidate = static_dir()
    if (candidate / _INDEX).is_file():
        return candidate
    return None


def bundle_version() -> Optional[str]:
    """Return the webapp version recorded alongside the bundle, if present."""
    bundle = find_bundle()
    if bundle is None:
        return None
    version_file = bundle / "VERSION"
    if not version_file.is_file():
        return None
    return version_file.read_text(encoding="utf-8").strip() or None
