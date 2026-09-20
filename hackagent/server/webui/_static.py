# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Locate the HackAgent web UI bundle (a static Next.js export).

The bundle is built from the ``hackagent-webapp`` repository and reaches an
installation by one of two routes, in this order:

1. **Bundled in the package tree** (``hackagent/server/webui/static``). This is
   how release binaries ship it: PyInstaller collects the directory via
   ``collect_data_files("hackagent")``, which preserves the package tree, so
   resolving relative to ``__file__`` works in a frozen build. It is how a
   source checkout gets one too, after ``scripts/build_webui.sh``.

2. **The ``hackagent-webui`` distribution**, installed by
   ``pip install 'hackagent[web]'``. Keeping the ~0.9 MB bundle out of the
   ``hackagent`` wheel means pip handles fetching, caching, mirrors and
   air-gapped wheelhouses, instead of a downloader written here.

Neither being present is a normal state for a plain source checkout, and the
caller is expected to say so rather than fail obscurely.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("hackagent.server.webui")

#: Marker file that distinguishes a real bundle from an empty placeholder dir.
_INDEX = "index.html"


def static_dir() -> Path:
    """Return the path the web UI bundle is expected at (may not exist)."""
    return Path(__file__).resolve().parent / "static"


def _installed_package_dir() -> Optional[Path]:
    """Return the bundle from an installed ``hackagent-webui``, if there is one."""
    try:
        from hackagent_webui import bundle_path
    except ImportError:
        return None
    try:
        return bundle_path()
    except RuntimeError:
        # Installed but built without assets: treat as absent so the caller's
        # "no bundle" guidance still applies.
        logger.warning("hackagent-webui is installed but contains no bundle")
        return None


def find_bundle() -> Optional[Path]:
    """Return the web UI directory, or ``None`` if this install has none.

    A bundle inside the package tree wins over an installed ``hackagent-webui``:
    it is what a release binary ships, and it must not be shadowed by whatever
    version happens to be in the environment.
    """
    candidate = static_dir()
    if (candidate / _INDEX).is_file():
        return candidate
    return _installed_package_dir()


def bundle_version() -> Optional[str]:
    """Return the webapp version recorded alongside the bundle, if present."""
    bundle = find_bundle()
    if bundle is None:
        return None
    version_file = bundle / "VERSION"
    if not version_file.is_file():
        return None
    return version_file.read_text(encoding="utf-8").strip() or None


def bundle_source() -> Optional[str]:
    """Return where the active bundle came from: ``package`` or ``installed``."""
    if (static_dir() / _INDEX).is_file():
        return "package"
    if _installed_package_dir() is not None:
        return "installed"
    return None
