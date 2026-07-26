# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Version lookup that also works from a frozen (PyInstaller) binary."""

import os
from importlib.metadata import PackageNotFoundError, version as _distribution_version

UNKNOWN_VERSION = "unknown"


def get_version() -> str:
    """Return the installed ``hackagent`` version.

    Frozen builds may ship without distribution metadata, so fall back to the
    ``HACKAGENT_BUILD_VERSION`` value baked in at packaging time.
    """
    try:
        return _distribution_version("hackagent")
    except PackageNotFoundError:
        return os.environ.get("HACKAGENT_BUILD_VERSION") or UNKNOWN_VERSION
