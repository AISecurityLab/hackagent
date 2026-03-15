# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
conftest.py for server/storage unit tests.

Pre-registers stub modules for optional heavy dependencies (rich, attrs, etc.)
so the storage modules can be imported and tested without a full dev install.
"""

import sys
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Stub heavy optional dependencies before any test module is imported.
# This allows the storage tests to run without the full hackagent dev extras.
# ---------------------------------------------------------------------------
_STUBS = [
    "rich",
    "rich.logging",
    "rich.console",
    "rich.theme",
    "rich.markup",
    "rich.text",
    "rich.highlighter",
    "rich.panel",
    "rich.table",
    "rich.progress",
    "rich.prompt",
    "rich.syntax",
    "rich.traceback",
    "rich.live",
]
for _mod in _STUBS:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()
