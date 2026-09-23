# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
conftest.py for server/webui unit tests.

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


# ---------------------------------------------------------------------------
# Keep the stubs out of the logging machinery.
#
# hackagent installs a ``rich.logging.RichHandler`` on the root logger at import
# time. With ``rich`` stubbed above, that handler is a MagicMock whose ``level``
# compares as a MagicMock, so ``logging.Logger.callHandlers`` raises TypeError
# on any real log call — turning a logged warning inside the code under test
# into a request failure. Drop anything that is not a genuine handler.
# ---------------------------------------------------------------------------
import logging  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _drop_stubbed_log_handlers():
    """Strip MagicMock handlers from every logger for the duration of a test."""
    manager = logging.Logger.manager
    loggers = [logging.getLogger()] + [
        lg for lg in manager.loggerDict.values() if isinstance(lg, logging.Logger)
    ]
    saved = {}
    for lg in loggers:
        stubbed = [h for h in lg.handlers if not isinstance(h, logging.Handler)]
        if stubbed:
            saved[lg] = list(lg.handlers)
            lg.handlers = [h for h in lg.handlers if isinstance(h, logging.Handler)]
    yield
    for lg, handlers in saved.items():
        lg.handlers = handlers
