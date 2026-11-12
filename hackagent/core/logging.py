# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Logger access for library code.

Library modules only obtain loggers; they never install handlers or set
levels. Handler configuration belongs to the application (the CLI does it in
:mod:`hackagent.interfaces.cli.logging_setup`).
"""

import logging
from collections.abc import Mapping

#: ``extra=`` for a log line whose fact a campaign progress event reports
#: too. The line still reaches every handler; the run activity relay skips
#: it, so the platform records the fact once, from the event.
REPORTED_AS_EVENT: Mapping[str, bool] = {"reported_as_event": True}


def get_logger(name: str) -> logging.Logger:
    """Return the logger called ``name`` without configuring it."""
    return logging.getLogger(name)


def reported_as_event(record: logging.LogRecord) -> bool:
    """Return whether ``record`` was logged with :data:`REPORTED_AS_EVENT`."""
    return bool(getattr(record, "reported_as_event", False))
